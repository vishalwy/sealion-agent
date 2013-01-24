var sqlite3 = require('sqlite3');

var Sealion = { };

Sealion.createTableStmt = 
        'CREATE TABLE IF NOT EXISTS repository \
            ( \
            row_id INTEGER PRIMARY KEY, \
            date_time TEXT, \
            result TEXT )';

Sealion.insertDataStmt = 
        'INSERT INTO repository(date_time, result) VALUES(?,?)';

Sealion.dbPath = '../etc/dbs/RepositoryDB.db';

Sealion.StoreDataInDb = function () {
    var tempThis = this;
    this.db = new sqlite3.Database(Sealion.dbPath, function(error) {
        if(error) {
            console.log("error in opening db");
        } else {
            tempThis.db.run('PRAGMA journal_mode = WAL');
            tempThis.db.run('PRAGMA busy_timeout = 3000000');
                        
            tempThis.db.run(Sealion.createTableStmt, function(error) {
                if(error) {
                    console.log("Error in table creation!!!");
                }
            });
        }
    });
    
    this.db.on('error', function(error) { 
        console.log("found error in database operation");
    });
    
    this.db.on('unhandledException', function(error) {
        console.log("found unhandled exception in database operation");
    });    
};

Sealion.StoreDataInDb.prototype.getDb = function() {
    return this.db;
}

Sealion.StoreDataInDb.prototype.closeDb = function( ) {
    this.db.close();
}

Sealion.StoreDataInDb.prototype.insertData = function (data) {
    var tempThis = this;
    
    this.db.serialize( function () {
        var stmt = tempThis.db.prepare(Sealion.insertDataStmt);
        stmt.on('error', function(error) {
            console.log("sqlite prepared statement runtime error while deleting from DB");
        });
        
        stmt.on('unhandledException', function(error) {
           console.log("sqlite prepared statement unhandled exception");  
        });
                
        stmt.run(new Date().toJSON(), data, function(error) {
            if(error) {
                console.log("sqlite prepared statement stmt.run runtime error while inserting in DB");
            }
        });
        stmt.finalize();
    });
};

module.exports = Sealion.StoreDataInDb;
