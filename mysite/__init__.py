# Use PyMySQL as the MySQL/MariaDB driver when it's installed (on the server).
# mysqlclient can't be compiled on the shared host, so PyMySQL stands in for it.
try:
    import pymysql

    pymysql.version_info = (2, 2, 7, "final", 0)   # report a version Django accepts
    pymysql.install_as_MySQLdb()
except ImportError:
    pass   # locally we use SQLite, so PyMySQL isn't needed
