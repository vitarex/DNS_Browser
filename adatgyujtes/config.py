import configparser

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

def register_id():
    pass