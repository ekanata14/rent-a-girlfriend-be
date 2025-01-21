class Config:
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'dream'
    MYSQL_PASSWORD = 'dream'
    MYSQL_DB = 'rentagirlfriend'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
