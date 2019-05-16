import configparser
import os
import random
import string
import requests
import pdb
import sys
import nacl.pwhash
from enum import Enum

config = configparser.ConfigParser()
config.read('config.ini')

class ConfigTypes(Enum):
    DEFAULT = 1
    TEST = 2

class Config:
    def __init__(self, configType):
        self.configType = configType
        self.database_path = config[configType.name]['DATABASE_PATH']
        self.copied_database_path = config[configType.name]['COPIED_DATABASE_PATH']
        self.zipped_db_name = config[configType.name]['ZIPPED_DB_NAME']
        self.sas_url = config[configType.name]['SAS_URL']
        self.adatgyujtes_id = config[configType.name]['ADATGYUJTES_ID']
        self.password = config[configType.name]['PASSWORD'].encode()

    def change_password(self, newpw):
        newhash = hashpw(newpw)
        self.password = newhash.encode()
        config.set(self.configType.name, 'PASSWORD', newhash)
        config.write(open('config.ini', 'w'))

    def set_database_path(self):
        # Getting privadome.db location if it uses same interpreter as this script
        python_dir_path = os.path.dirname(sys.executable)
        db_path = os.path.join(python_dir_path, "Lib", "site-packages", "privadome", "database", "privadome.db")
        self.database_path = db_path
        config.set(self.configType.name, 'DATABASE_PATH', db_path)
        config.write(open('config.ini', 'w'))

def hashpw(pw):
    return nacl.pwhash.str(pw.encode()).decode()

def init_device():
    print("Credential: ")
    credential = input()
    configure(credential)

def configure(credential = None):
    gen_id = random_string()
    result = requests.post(url=config['REGISTER']['REGISTER_URL'], json={"generationCredential": credential, "id": gen_id})
    if result.ok:
        if result.json()['id'] == gen_id:
            config.set('DEFAULT', 'ADATGYUJTES_ID', gen_id)

            password = 'admin'
            config.set('DEFAULT', 'PASSWORD', hashpw(password))

            try:
                import privadome
                # TODO
                config.set('DEFAULT', 'DATABASE_PATH', privadome.__file__)

                # Getting privadome.db location if it uses same interpreter as this script
                PYTHON_DIR_PATH = os.path.dirname(sys.executable)
                DATABASE_PATH = os.path.join(PYTHON_DIR_PATH, "Lib", "site-packages", "privadome", "database", "privadome.db")
                print("PRIVADOME DB_PATH - : ", DATABASE_PATH)
                COPIED_DATABASE_PATH = "copy.db"
                config.set('DEFAULT', 'DATABASE_PATH', DATABASE_PATH) #TODO config.set_database_path()
                config.set('DEFAULT', 'COPIED_DATABASE_PATH', COPIED_DATABASE_PATH)

            except ImportError as e:
                print("Configure hiba. ", e)

            config.write(open('config.ini', 'w'))
            print('Eszköz sikeresen regisztrálva.')
            print('Jelszó: ', password)
        else:
            print('Nem sikerült regisztrálni az eszközt.', result.content)
    else:
        print('Nem sikerült regisztrálni az eszközt.', result.content)
        pdb.set_trace()
            

def random_string(length = 16):
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))