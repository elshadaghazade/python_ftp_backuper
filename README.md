# Python FTP Backuper

Connects to the ftp server, takes full and incremental backup and pushes to the default git repo

### Prerequisites

- Python 2.7+
- PIP
- Linux

### Installing

```
git clone https://github.com/elshadaghazade/python_ftp_backuper.git
pip install -r package.txt
mv .env_sample .env
```
Than you have to edit .env file

```
ftp_host=[type here ftp host]
ftp_user=[type here ftp user]
ftp_pass=[type here ftp password]
root_dir=[type here remote root directory where we have to start scanning (default is /)]
```

## And run:

```
python main.py
``` 

## Authors

* **Elshad Agayev** - *Fullstack developer* - [PurpleBooth](https://elshadaghazade.wordpress.com/about/)
