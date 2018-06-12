from incremental_backuper import IncrementalBackuper
import os

if __name__ == "__main__":
    with IncrementalBackuper(ftp_host=os.environ['ftp_host'], ftp_user=os.environ['ftp_user'], ftp_pass=os.environ['ftp_pass'], root_dir=os.environ['root_dir']) as obj:
        try:
            obj.take_backup()
        except Exception as err:
            print(err)