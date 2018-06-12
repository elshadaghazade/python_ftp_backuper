from ftplib import FTP
import re
import time
import datetime
from collections import namedtuple
import os
from copy import deepcopy
from pathlib import Path
import sys
import pickle
import zipfile
import shutil
import subprocess
from dotenv import load_dotenv

load_dotenv()


class IncrementalBackuper:
    def __init__(self, ftp_host, ftp_user, ftp_pass, root_dir="/"):
        self.ftp_host = ftp_host
        self.ftp_user = ftp_user
        self.ftp_pass = ftp_pass
        self.files = []
        self.root_dir = root_dir
        self.local_root_dir = f"{str(Path.home())}/.seru_backup/{self.ftp_host}/{self.ftp_user}/{datetime.datetime.now().year}/{datetime.datetime.now().month}"
        self.statistics = {
            'folders': 0,
            'files': 0,
            'size': 0
        }

    def __enter__(self):
        return self.connect()
    
    def __exit__(self, *args, **kwargs):
        self.close()
    
    def get_stat (self):
        stat = {
            "incremental": 0,
            "full": {
                "prefix": "",
                "downloaded": 0,
                "zipped": 0,
                "folder_removed": 0,
                "uploaded": 0
            },
            "incremental": []
        }

        filename = f"{self.local_root_dir}/.stat"

        if not os.path.isfile(filename):
            with open(filename, "wb") as f:
                pickle.dump(stat, f)

        with open(filename, "rb") as f:
            stat = pickle.load(f)
        return stat
    
    def save_stat(self, stat):
        with open(f"{self.local_root_dir}/.stat", "wb") as f:
            pickle.dump(stat, f)

    def take_backup(self, path = ""):
        self.ftp.cwd(self.root_dir + path)
        self.ftp_mlsd(path=path)

    def ftp_mlsd(self, path):
        files = self.ftp.mlsd()
        for file in files:
            sys.stdout.flush()
            print(f"""\rFiles: {self.statistics['files']} | Folders: {self.statistics['folders']} | Total size: {self.statistics['size']} | Scanning: {path}""", end="")
            if file[1]['type'] == 'dir':
                self.files.append({
                    "is_dir": True,
                    "path": f"{path}/{file[0]}",
                    "dir": path,
                    "filename": file[0],
                    "created_at": file[1]['modify'],
                    "filesize": 0
                })
                self.take_backup(f"{path}/{file[0]}")
                self.statistics['folders'] += 1
            elif file[1]['type'] == 'file':
                self.files.append({
                    "is_dir": False,
                    "path": f"{path}/{file[0]}",
                    "dir": path,
                    "filename": file[0],
                    "created_at": file[1]['modify'],
                    "filesize": file[1]['size']
                })
                self.statistics['files'] += 1
                self.statistics['size'] += int(file[1]['size'])

    def download(self):
        if not os.path.isdir(self.local_root_dir):
            os.makedirs(self.local_root_dir)
        
        stat = self.get_stat()

        # check fullbackup
        if not stat['full']['prefix']:
            return self.take_full_backup()
        elif not stat['full']['downloaded']:
            return self.take_full_backup(action='redownload', prefix=stat['full']['prefix'])
        elif not stat['full']['zipped'] or not stat['full']['folder_removed'] or not stat['full']['uploaded']:
            self.take_full_backup(action="finish", prefix=stat['full']['prefix'])
            self.take_incremental_backup()

    def save_list(self, fileslist):
        if not os.path.isdir(self.local_root_dir):
            os.makedirs(self.local_root_dir)

        with open(f"{self.local_root_dir}/.list", "wb") as f:
            dump = pickle.dump(fileslist, f)
    
    def get_list(self):
        mylist = []
        with open(f"{self.local_root_dir}/.list", "rb") as f:
            mylist = pickle.load(f)
        return mylist


    def take_incremental_backup(self):
        if not os.path.isdir(self.local_root_dir):
            os.makedirs(self.local_root_dir)

        stat = self.get_stat()
        incremental = stat['incremental'] + 1
        inc_stat = {
            "prefix": "",
            "downloaded": 0,
            "zipped": 0,
            "folder_removed": 0,
            "uploaded": 0
        }

        stat['incremental'].append(inc_stat)
        self.save_stat(stat)

        folder_name = f"incremental_{incremental}_{datetime.datetime.now().year}_{datetime.datetime.now().month}_{datetime.datetime.now().day}_{datetime.datetime.now().hour}_{datetime.datetime.now().minute}_{datetime.datetime.now().second}"
        inc_stat['prefix'] = local_root_dir = f"{self.local_root_dir}/{folder_name}"
        self.save_stat(stat)

        files = self.get_list()
        incr_files = []
        for i in self.files:
            if not i in files:
                incr_files.append(i)

        # save files list in the .list file
        self.save_list(self.files)

        for index, file in enumerate(incr_files):
            # if node is dir
            if file['is_dir']:
                path = f"{local_root_dir}{file['dir']}"
                print("Creating directory:", path)
                # create directory if not exists
                if not os.path.isdir(path):
                    os.makedirs(path)
            # if node is file
            else:
                path = f"{local_root_dir}/{file['dir']}"
                if not os.path.isdir(path):
                    print("Creating directory:", path)
                    os.makedirs(path)

                print("Changing local directory:", path)
                os.chdir(f"{local_root_dir}{file['dir']}")
                # if file not exists
                if not os.path.isfile(file['filename']):
                    # switch to directory of file
                    path = f"{self.root_dir}{file['dir']}"
                    print("CWD", path)
                    self.ftp.cwd(path)
                    # download and create file
                    print("RETR", file['filename'])
                    
                    with open(file['filename'], "wb") as f:
                        # downloading file
                        try:
                            self.ftp.retrbinary(f"RETR {file['filename']}", f.write, blocksize=4096)
                        except Exception as err:
                            print(err)

        inc_stat['downloaded'] = 1
        self.save_stat(stat)
        self.zip_folder(local_root_dir, local_root_dir + ".zip")
        inc_stat['zipped'] = 1
        inc_stat['folder_removed'] = 1
        self.save_stat(stat)
        self.git_push(local_root_dir)
        inc_stat['uploaded'] = 1
        self.save_stat(stat)
        


    
    def take_full_backup (self, action = "", prefix = ""):
        
        if action == "redownload" and prefix:
            folder_name = prefix
        else:
            folder_name = f"full_{datetime.datetime.now().year}_{datetime.datetime.now().month}_{datetime.datetime.now().day}_{datetime.datetime.now().hour}_{datetime.datetime.now().minute}_{datetime.datetime.now().second}"

        local_root_dir = f"{self.local_root_dir}/{folder_name}"

        # save files list in the .list file
        self.save_list(self.files)
        # stat
        stat = self.get_stat()
        stat['full']['prefix'] = local_root_dir
        self.save_stat(stat)

        if not action or action == 'redownload':
            cnt_files = 0
            cnt_folders = 0
            cnt_bytes = 0
            
            for index, file in enumerate(self.files):
                # if node is dir
                if file['is_dir']:
                    cnt_folders += 1
                    path = f"{local_root_dir}{file['dir']}"
                    # create directory if not exists
                    if not os.path.isdir(path):
                        print("Creating directory:", path)
                        os.makedirs(path)
                # if node is file
                else:
                    cnt_files += 1
                    path = f"{local_root_dir}/{file['dir']}"
                    if not os.path.isdir(path):
                        print("Creating directory:", path)
                        os.makedirs(path)

                    print("Changing local directory:", path)
                    os.chdir(f"{local_root_dir}{file['dir']}")
                    fstat = None
                    if os.path.isfile(file['filename']):
                        fstat = os.stat(file['filename'])
                    # if file not exists or file is older or filesize is different then overwrite
                    if not os.path.isfile(file['filename']) or (fstat and fstat.st_size != file['filesize']) or (fstat and int(fstat.st_mtime) != int(file['created_at'])):
                        # switch to directory of file
                        path = f"{self.root_dir}{file['dir']}"
                        print("CWD", path)
                        self.ftp.cwd(path)
                        # download and create file
                        print("RETR", file['filename'])
                        
                        with open(file['filename'], "wb") as f:
                            # downloading file
                            try:
                                self.ftp.retrbinary(f"RETR {file['filename']}", f.write, blocksize=4096)
                                cnt_bytes += int(fstat.st_size)
                            except Exception as err:
                                print(err)

                print(f"Files: {cnt_files}/{self.statistics['files']} | Folders: {cnt_folders}/{self.statistics['folders']} | Total size: {cnt_bytes}/{self.statistics['size']}")

            stat = self.get_stat()
            stat['full']['downloaded'] = 1
            self.save_stat(stat)

        elif action == 'finish':
            stat = self.get_stat()
            if not os.path.isfile(local_root_dir + ".zip") or not stat['full']['zipped'] or not stat['full']['folder_removed']:
                
                self.zip_folder(local_root_dir, local_root_dir + ".zip")                
                stat['full']['zipped'] = 1
                stat['full']['folder_removed'] = 1
                self.save_stat(stat)

            stat = self.get_stat()
            if not stat['full']['uploaded']:
                self.git_push(local_root_dir)
                stat['full']['uploaded'] = 1
                self.save_stat(stat)

    def git_push(self, commit):
        os.chdir(self.local_root_dir)
        print("\ncommitting and pushing to git")
        subprocess.call('git add .', shell=True)
        subprocess.call(f'git commit -m "{commit}"', shell=True)
        subprocess.call('git push origin master', shell=True)
        

    def connect(self, initial_dir = "/"):
        self.ftp = FTP(self.ftp_host)
        self.ftp.login(self.ftp_user, self.ftp_pass)
        self.ftp.cwd(self.root_dir)
        print("connected")
        return self
    
    def close(self):
        self.download()
        self.ftp.close()

    def zip_folder(self, folder_path, output_path):
        """Zip the contents of an entire folder (with that folder included
        in the archive). Empty subfolders will be included in the archive
        as well.
        """

        if not os.path.isdir(folder_path):
            return

        print("Zipping folder", folder_path)
        parent_folder = os.path.dirname(folder_path)
        # Retrieve the paths of the folder contents.
        contents = os.walk(folder_path)
        zip_file = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)
        try:
            for root, folders, files in contents:
                # Include all subfolders, including empty ones.
                for folder_name in folders:
                    absolute_path = os.path.join(root, folder_name)
                    relative_path = absolute_path.replace(parent_folder + '\\',
                                                        '')
                    print("Adding '%s' to archive." % absolute_path)
                    zip_file.write(absolute_path, relative_path)
                for file_name in files:
                    absolute_path = os.path.join(root, file_name)
                    relative_path = absolute_path.replace(parent_folder + '\\',
                                                        '')
                    print("Adding '%s' to archive." % absolute_path)
                    zip_file.write(absolute_path, relative_path)
            print("'%s' created successfully." % output_path)
        except IOError as message:
            print(message)
            sys.exit(1)
        except OSError as message:
            print(message)
            sys.exit(1)
        except zipfile.BadZipfile as message:
            print(message)
            sys.exit(1)
        finally:
            zip_file.close()
            shutil.rmtree(folder_path)