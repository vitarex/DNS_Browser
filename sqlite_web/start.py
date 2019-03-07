import os
from sqlite_web import initialize_app

db_path = os.getcwd() + "/privadome.db"
initialize_app(db_path)