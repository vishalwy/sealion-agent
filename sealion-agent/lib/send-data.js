/* 
This module is used to send data to server and handles corresponding errors
This module is class representation for sending data
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var serverOption = require('../etc/config/server-config.json').serverDetails;
var dataPath = require('../etc/config/paths-config.json').dataPath;
var Sqlite3 = require('./sqlite-wrapper.js');
var global = require('./global.js');
var updateConfig = require('./update-config.js');
var authenticate = require('./authentication.js');
var logData = require('./log.js');

// variable to check if SQLite DB should be checked for sending stored data to server
var needCheckStoredData = true;

/** @constructor */
function SendData(sqliteObj) {
    this.dataToInsert = '';
    this.sqliteObj = sqliteObj;
    this.activityID = '';
};

/*
function handles error by storing sending-failed data in SQLite DB
*/
SendData.prototype.handleError = function() {
    // function to insert data
    this.sqliteObj.insertData(this.dataToInsert, this.activityID);
    needCheckStoredData = true;
}

// function to insert erroneous data into SQLite. this data wiull never be sent to server
SendData.prototype.handleErroneousData = function(data, activityID) {
    this.sqliteObj.insertErroneousData(data, activityID);
}

// function to delete data with some particular activityID. 
// Used in case activity is removed by user on UI so associated data needs to be removed as well
SendData.prototype.deleteDataWithActivityID = function(activityID) {
    var tempSqliteObj = new Sqlite3();
    var tempDB = tempSqliteObj.getDb();
    var self = this;
    
    tempDB.run('DELETE FROM repository WHERE activityID = ?', activityID, function(error){
        if(error) {
            logData("error in deleting activity data from DB");
        } else {
            process.nextTick(function () {
                self.sendStoredData();
            });
        }
    });
    tempSqliteObj.closeDb();
}

// function deletes data from SQLite with particular row_id
// used to delete rows in case duplicates are found
SendData.prototype.deleteData = function(self, rowId) {
    var tempSqliteObj = new Sqlite3();
    var tempDB = tempSqliteObj.getDb();
    var self =  this;
    tempDB.run('DELETE FROM repository WHERE row_id = ?', rowId, function(error){
        if(error) {
            logData("error in deleting data from DB");
        } else {
            process.nextTick(function () {
                self.sendStoredData();
            });
        }
    });
    tempSqliteObj.closeDb();
}

// function to send stored data
SendData.prototype.sendStoredData = function() {
    var sobj = new Sqlite3();
    var db = sobj.getDb();
    var tempThis = this;
    
    if(db) {
        db.all('SELECT row_id, activityID, date_time, result FROM repository LIMIT 0,1', function(error, rows) {
            
            if(error) {
                needCheckStoredData = true;
                logData("error in retreiving data");
            } else {
                if(rows.length > 0) {
                    
                    var path = dataPath + rows[0].activityID;
                    var url = serverOption.sourceURL + path;
                    var toSend = JSON.parse(rows[0].result);
                    var sessionId = global.sessionCookie;
                    var sendOptions = {
                          'uri' : url
                        , 'json' : toSend
                    };
                    
                    if(sessionId == '') {
                        needCheckStoredData = true;
                        return;
                    }
                    
                    global.request.post(sendOptions, function(err, response, data) {
                        if(err) {
                            needCheckStoredData = true;
                            logData("Error in Sending stored data");
                        } else {
                            var bodyJSON = response.body;
                            switch(response.statusCode) {
                                case 200 : {
                                        tempThis.deleteData(tempThis, rows[0].row_id);
                                    }
                                    break;
                                case 400 : {
                                        needCheckStoredData = true;
                                        switch(bodyJSON.code) {
                                            case 230011 : {
                                                    logData('Sealion-Agent Error#440001: Payload Missing in stored data');
                                                    tempThis.handleErroneousData(rows[0].result, rows[0].activityID);        
                                                    tempThis.deleteData(tempThis, rows[0].row_id); 
                                                }
                                                break;
                                            case 230014 : {
                                                    logData('Sealion-Agent Error#440002: improper ActivityID, deleting from repository');
                                                    tempThis.deleteDataWithActivityID(rows[0].activityID);
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                case 401 : {
                                        needCheckStoredData = true;
                                        switch(bodyJSON.code) {
                                            case 230012 : {
                                                    logData('Sealion-Agent Error#440003: Agent not allowed to send data with ActivityID: ' + 
                                                            rows[0].activityID + ', deleting from repository');
                                                    tempThis.deleteDataWithActivityID(rows[0].activityID);
                                                }
                                                break;
                                            case 220001 : {
                                                    logData('Sealion-Agent Error#440005: Authentication Failed, Needs reauthentication');
                                                    authenticate.reauthenticate(sessionId);
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                case 409 : {
                                        needCheckStoredData = true;
                                        switch(bodyJSON.code) {
                                            case 230013 : {
                                                    logData('Sealion-Agent Error#440004: Duplicate data. Data deleted from repository');
                                                    tempThis.deleteData(tempThis, rows[0].row_id);
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                default : {
                                    needCheckStoredData = true;
                                    }
                                    break;
                            }
                        }
                    });
                } else {
                    needCheckStoredData = false;
                }
            }
        });
        sobj.closeDb();
    }
}

// function to send command result
SendData.prototype.dataSend = function (result) {
    var tempThis = this;
    
    var toSend = {
                  'returnCode' : result.code
                , 'timestamp' : result.timeStamp
                , 'data' : result.output };
                
    this.dataToInsert = JSON.stringify(toSend);
    this.activityID = result.activityDetails._id;
    
    var path = dataPath + result.activityDetails._id;
    var url = serverOption.sourceURL + path;
    var sessionId = global.sessionCookie;
    var sendOptions = {
          'uri' : url
        , 'json' : toSend
    };
    
    if(sessionId == '') {
        tempThis.handleError();
        return;
    }
    
    
    global.request.post(sendOptions, function(err, response, data) {
        
        if(err) {
            tempThis.handleError();
        } else {
            var bodyJSON = response.body;

            switch(response.statusCode) {
                case 200 : {
                        if(needCheckStoredData) {
                            needCheckStoredData = false;
                            tempThis.sendStoredData();
                        }    
                    }
                    break;
                case 400 : {
                        if(bodyJSON.code) {
                            switch(bodyJSON.code) {
                                case 230011 : {
                                        logData('Sealion-Agent Error#430001: Payload Missing');
                                        tempThis.handleErroneousData(tempThis.dataToInsert, tempThis.activityID);
                                    }
                                    break;
                                case 230014 : {
                                        logData('Sealion-Agent Error#430002: improper ActivityID, updating config-file');
                                        updateConfig();
                                    }
                                    break;
                                default : {
                                        tempThis.handleError();    
                                    }
                            }
                        } else {
                            tempThis.handleError();
                        }
                    }
                    break;
                case 401 : {
                        if(bodyJSON.code) {
                            switch(bodyJSON.code) {
                                case 230012 : {
                                        logData('Sealion-Agent Error#430003: Agent not allowed to send data with ActivityID: ' + result.activityDetails._id + ', updating config-file');
                                            updateConfig();
                                    }
                                    break;
                                case 220001 : {
                                        logData('Sealion-Agent Error#430005: Authentication Failed, Needs reauthentication');
                                        tempThis.handleError();
                                        authenticate.reauthenticate(sessionId);
                                    }
                                    break;
                                default : {
                                        tempThis.handleError();
                                    }
                                    break;
                            }    
                        } else {
                            tempThis.handleError();
                        }
                    }
                    break;
                case 409 : {
                        logData('Sealion-Agent Error#430004: Duplicate data. Data dropped');                   
                    }
                    break;
                default: {
                        tempThis.handleError();    
                    }
                    break;
            }
        }
    });
}

module.exports = SendData;
