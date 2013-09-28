/* 
module to handle basic SQLite operations
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>
 (c) Webyog Inc.

*********************************************/

var sqlite3 = require('sqlite3');
var path = require('path');
var logData = require('./log.js');
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

var deleteDataStmt =
        'DELETE FROM repository WHERE row_id = ?';

var deleteDataWithActivityIdStmt =
    'DELETE FROM repository WHERE activityID = ?';

var dbPath = path.resolve(__dirname, '../var/dbs/RepositoryDB.db');

/** @constructor */
function StoreDataInDb() {
    var tempThis = this;
    this.db = new sqlite3.Database(dbPath, function(error) {
        if(error) {
            logData("Error in opening db");
        } else {
            tempThis.db.run('PRAGMA journal_mode = WAL');
            tempThis.db.run('PRAGMA busy_timeout = 3000000');
                        
            tempThis.db.run(createTableStmt, function(error) {
                if(error) {
                    logData("Error in table creation!!!");
                }
            });
            
            tempThis.db.run(createErroneousTableStmt, function(error) {
                if(error) {
                    logData("Error in table creation!!!");
                }
            });
        }
    });
    
    this.db.on('error', function(error) { 
        logData("Found error in database operation " + error);
    });
    
    this.db.on('unhandledException', function(error) {
        logData("Found unhandled exception in database operation");
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
            logData("SQLite prepared statement runtime error while inserting erroneous data in DB");
        });
        
        stmt.on('unhandledException', function(error) {
           logData("SQLite prepared statement unhandled exception");
        });
                
        stmt.run(new Date().toJSON(), activityID, data, function(error) {
            if(error) {
                logData("Sqlite prepared statement stmt.run runtime error while inserting in DB");
            }
        });
        stmt.finalize();
    });
}

StoreDataInDb.prototype.deleteData = function(rowId, contextObj, callback) {
    var tempThis = this;
    this.db.serialize( function() {
        var stmt = tempThis.db.prepare(deleteDataStmt);
        stmt.on('error', function(error){
            logData("SQLite prepared statement runtime error while deleting data from DB");
        });

        stmt.on('unhandledException', function(error) {
            logData("SQLite prepared statement unhandled exception");
        });

        stmt.run(rowId, function(error){
            if(error) {
                logData("Sqlite prepared statement stmt.run runtime error while deleting from DB");
            } else if( contextObj && callback && typeof callback === 'function') {
                process.nextTick(function () {
                    callback.apply(contextObj);
                });
            }
        });
        stmt.finalize();
    });
}

StoreDataInDb.prototype.deleteDataWithActivityId = function(activityId, contextObj, callback) {
    var tempThis = this;
    this.db.serialize( function() {
        var stmt = tempThis.db.prepare(deleteDataWithActivityIdStmt);
        stmt.on('error', function(error){
            logData("SQLite prepared statement runtime error while deleting data with activityID from DB");
        });

        stmt.on('unhandledException', function(error) {
            logData("SQLite prepared statement unhandled exception");
        });

        stmt.run(activityId, function(error){
            if(error) {
                logData("Sqlite prepared statement stmt.run runtime error while deleting data with activityID from DB");
            } if( contextObj && callback && typeof callback === 'function') {
                process.nextTick(function () {
                    callback.apply(contextObj);
                });
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
            logData("Sqlite prepared statement runtime error while inserting data in DB");
        });
        
        stmt.on('unhandledException', function(error) {
           logData("Sqlite prepared statement unhandled exception");  
        });
                
        stmt.run(new Date().toJSON(), activityID, data, function(error) {
            if(error) {
                logData("Sqlite prepared statement stmt.run runtime error while inserting in DB");
            }
        });
        stmt.finalize();
    });
};

module.exports = StoreDataInDb;
