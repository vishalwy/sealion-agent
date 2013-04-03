/* 
module to handle basic SQLite operations
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var sqlite3 = require('sqlite3');
var path = require('path');

/** @const */
var createTableStmt = 
        'CREATE TABLE IF NOT EXISTS repository \
            ( \
            row_id INTEGER PRIMARY KEY, \
            activityID TEXT, \
            date_time TEXT, \
            result TEXT )';
            
/** @const */            
var createErroneousTableStmt = 
        'CREATE TABLE IF NOT EXISTS erroneousRepository \
            ( \
            row_id INTEGER PRIMARY KEY, \
            activityID TEXT, \
            date_time TEXT, \
            result TEXT )';

var insertDataStmt = 
        'INSERT INTO repository(date_time, activityID, result) VALUES(?,?,?)';

var insertErroneousDataStmt = 
        'INSERT INTO erroneousRepository(date_time, activityID, result) VALUES(?,?,?)';

var dbPath = path.resolve(__dirname, '../var/dbs/RepositoryDB.db');

/** @constructor */
function StoreDataInDb() {
    var tempThis = this;
    this.db = new sqlite3.Database(dbPath, function(error) {
        if(error) {
            console.log("error in opening db");
        } else {
            tempThis.db.run('PRAGMA journal_mode = WAL');
            tempThis.db.run('PRAGMA busy_timeout = 3000000');
                        
            tempThis.db.run(createTableStmt, function(error) {
                if(error) {
                    console.log("Error in table creation!!!");
                }
            });
            
            tempThis.db.run(createErroneousTableStmt, function(error) {
                if(error) {
                    console.log("Error in table creation!!!");
                }
            });
        }
    });
    
    this.db.on('error', function(error) { 
        console.log("found error in database operation " + error);
    });
    
    this.db.on('unhandledException', function(error) {
        console.log("found unhandled exception in database operation");
    });    
};

StoreDataInDb.prototype.getDb = function() {
    return this.db;
}

StoreDataInDb.prototype.closeDb = function( ) {
    this.db.close();
}

StoreDataInDb.prototype.insertErroneousData = function(data, activityID) {
    var tempThis = this;
    this.db.serialize( function () {
    var stmt = tempThis.db.prepare(insertErroneousDataStmt);
        stmt.on('error', function(error) {
            console.log("sqlite prepared statement runtime error while deleting from DB");
        });
        
        stmt.on('unhandledException', function(error) {
           console.log("sqlite prepared statement unhandled exception");  
        });
                
        stmt.run(new Date().toJSON(), activityID, data, function(error) {
            if(error) {
                console.log("sqlite prepared statement stmt.run runtime error while inserting in DB");
            }
        });
        stmt.finalize();
    });
}


StoreDataInDb.prototype.insertData = function (data, activityID) {
    var tempThis = this;
    this.db.serialize( function () {
        var stmt = tempThis.db.prepare(insertDataStmt);
        stmt.on('error', function(error) {
            console.log("sqlite prepared statement runtime error while deleting from DB");
        });
        
        stmt.on('unhandledException', function(error) {
           console.log("sqlite prepared statement unhandled exception");  
        });
                
        stmt.run(new Date().toJSON(), activityID, data, function(error) {
            if(error) {
                console.log("sqlite prepared statement stmt.run runtime error while inserting in DB");
            }
        });
        stmt.finalize();
    });
};

module.exports = StoreDataInDb;
