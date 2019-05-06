import configparser
import random
import string
import requests
import pdb

config = configparser.ConfigParser()
config.read('config.ini')

CONFIG_DEFAULT = {
    'DATABASE_PATH': config['DEFAULT']['DATABASE_PATH'],
    'ZIPPED_DB_NAME': config['DEFAULT']['ZIPPED_DB_NAME'],
    'SAS_URL': config['DEFAULT']['SAS_URL'],
    'ADATGYUJTES_ID': config['DEFAULT']['ADATGYUJTES_ID'],
    'PASSWORD': config['DEFAULT']['PASSWORD']
}

CONFIG_TEST = {
    'DATABASE_PATH': config['TEST']['DATABASE_PATH'],
    'ZIPPED_DB_NAME': config['TEST']['ZIPPED_DB_NAME'],
    'SAS_URL': config['TEST']['SAS_URL'],
    'ADATGYUJTES_ID': config['TEST']['ADATGYUJTES_ID'],
    'PASSWORD': config['DEFAULT']['PASSWORD']
}

def configure(credential):
    gen_id = random_string()
    result = requests.post(url=config['REGISTER']['REGISTER_URL'], json={"generationCredential": credential, "id": gen_id})
    if result.ok:
        if result.json()['id'] == gen_id:
            config.set('DEFAULT', 'ADATGYUJTES_ID', gen_id)

            password = random_string(8)
            config.set('DEFAULT', 'PASSWORD', password)

            try:
                import privadome
                # TODO
                config.set('DEFAULT', 'DATABASE_PATH', privadome.__file__)
            except ImportError as e:
                print(e)

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