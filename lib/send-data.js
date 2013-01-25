var https = require('https');
var serverOption = require('../etc/config/server-config.js');
var Sqlite3 = require('./sqlite-wrapper.js');

var Sealion = { };
var needCheckStoredData = true;


Sealion.SendData = function (sqliteObj) {
    this.dataToInsert = '';
    this.sqliteObj = sqliteObj;
};

Sealion.SendData.prototype.handleError = function() {
    this.sqliteObj.insertData(this.dataToInsert);
    needCheckStoredData = true;
}

Sealion.SendData.prototype.sendStoredData = function() {
    var sobj = new Sqlite3();
    var db = sobj.getDb();
    var tempThis = this;
    
    if(db) {
        db.all('SELECT * FROM repository LIMIT 0,1', function(error, rows) {
            
            if(error) {
                needCheckStoredData = true;
                console.log("error in retreiving data");
            } else {
                if(rows.length > 0) {
                    console.log(rows[0].row_id);
                    var request = https.request(serverOption, function(response) {
                        var post_response = '';        
                        
                        response.on('data', function(dataChunk) {
                            post_response += dataChunk;
                        });    
                    
                        response.on('end', function(data) {
                            if(response.statusCode === 200) {
                                var tempSqliteObj = new Sqlite3();
                                var tempDB = tempSqliteObj.getDb();
                                tempDB.run('DELETE FROM repository WHERE row_id = ?', rows[0].row_id, function(error){
                                    if(error) {
                                        console.log("error in deleting data from DB");
                                    } else {
                                        process.nextTick(function () {
                                            tempThis.sendStoredData();
                                        });
                                    }
                                });
                                tempSqliteObj.closeDb();
                            } else {
                                needCheckStoredData = true;
                            }
                        });
                    });
                
                    request.on('error', function(error) {
                        needCheckStoredData = true;
                        console.log("Error in Sending stored data");
                    });
                    
                    request.on('uncaughtException', function(error) {
                        needCheckStoredData = true;
                        console.log("uncaught exception in sending stored data");
                    });
                    
                    request.write(rows[0].result);
                    request.end();                        
                } else {
                    needCheckStoredData = false;
                }
            }
        });
        sobj.closeDb();
    }
}

Sealion.SendData.prototype.dataSend = function (data) {
    var tempThis = this;
    
    this.dataToInsert = data;
    
    var tempFunction = function(error) {
        tempThis.handleError();
    };
    
    var request = https.request(serverOption, function(response) {
        var post_response = '';
        
        response.on('data', function(dataChunk) {
            post_response += dataChunk;
        });
        
        response.on('end', function(data) {
            if(response.statusCode !== 200) {
                tempThis.handleError();
            } else {
                if(needCheckStoredData) {
                    needCheckStoredData = false;
                    tempThis.sendStoredData();
                }
            }
        });
        
        response.on('error', function(error) {
            tempThis.handleError();
        });
        
        response.on('uncaughtException', function(error) {
            tempThis.handleError();
        });
    });
    
    request.write(data);
    request.end();
    
    request.on('error', function(error) {
        tempThis.handleError();
    });
    
    request.on('uncaughtException', function(error) {
        tempThis.handleError();
    });
}

module.exports = Sealion.SendData;
