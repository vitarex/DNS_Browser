import configparser
import os
import random
import string
import requests
import pdb
import sys
import nacl.pwhash
from enum import Enum

COPIED_DB_PATH = 'privadome_copy.db'

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
        

def hashpw(pw):
    return nacl.pwhash.str(pw.encode()).decode()

def init_device():
    print('Credential: ')
    credential = input()
    configure_default(credential)

def configure_test():
    config.set('TEST', 'ADATGYUJTES_ID', 'tesztID')

    password = 'admin'
    config.set('TEST', 'PASSWORD', hashpw(password))

    print('Teszt DB path:')
    config.set('TEST', 'DATABASE_PATH', input())

    config.write(open('config.ini', 'w'))
    
    print('Teszt környezet sikeresen felállítva.')

def configure_default(credential: str = None):
    gen_id = random_string()
    result = requests.post(url=config['REGISTER']['REGISTER_URL'], json={'generationCredential': credential, 'id': gen_id})
    if result.ok:
        if result.json()['id'] == gen_id:
            config.set('DEFAULT', 'ADATGYUJTES_ID', gen_id)

            password = 'admin'
            config.set('DEFAULT', 'PASSWORD', hashpw(password))

            try:
                import privadome
                print(privadome.__path__)
                db_path = os.path.join(privadome.__path__[0], 'database', 'privadome.db')
                if not os.path.exists(db_path):
                    raise AssertionError
                config.set('DEFAULT', 'DATABASE_PATH', db_path)
            except Exception as e:
                print(e)
                raise e

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