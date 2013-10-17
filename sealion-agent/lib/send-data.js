/* 
This module is used to send data to server and handles corresponding errors
This module is class representation for sending data
*/

/*********************************************

 (c) Webyog, Inc.

*********************************************/

var config = require('../etc/config/sealion-config.json');
var serverOption = config.serverDetails;
var dataPath = config.dataPath;
var Sqlite3 = require('./sqlite-wrapper.js');
var global = require('./global.js');
var updateConfig = require('./update-config.js');
var authenticate = require('./authentication.js');
var logData = require('./log.js');
var services = require('./execute-services.js');
var uninstallSelf = require('./uninstall-self.js');

// variable to check if SQLite DB should be checked for sending stored data to server
var needCheckStoredData = true;

/** @constructor */
function SendData(sqliteObj) {
    this.sqliteObj = sqliteObj;
    this.activityID = '';
};

/*
function handles error by storing sending-failed data in SQLite DB
*/
SendData.prototype.handleError = function(toSend) {
    // function to insert data
    var dataToInsert = JSON.stringify(toSend);
    this.sqliteObj.insertData(dataToInsert, this.activityID);
    needCheckStoredData = true;
}

// function to insert erroneous data into SQLite. this data wiull never be sent to server
SendData.prototype.handleErroneousData = function(toSend, activityID) {
    var data = JSON.stringify(toSend);
    this.sqliteObj.insertErroneousData(data, activityID);
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
                logData("Error in retrieving data");
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
                        sendOptions = null;
                        toSend = null;
                        return;
                    }
                    
                    global.request.post(sendOptions, function(err, response, data) {
                        if(err) {
                            needCheckStoredData = true;
                            logData("Error in Sending stored data");
                        } else {
                            var bodyJSON = response.body;
                            switch(response.statusCode) {
                                case 204 : {
                                        tempThis.sqliteObj.deleteData(rows[0].row_id, tempThis, tempThis.sendStoredData);
                                    }
                                    break;
                                case 400 : {
                                        switch(bodyJSON.code) {
                                            case 200002 : {
                                                    logData('SeaLion-Agent Error#440001: Payload Missing in stored data');
                                                    tempThis.handleErroneousData(rows[0].result, rows[0].activityID);        
                                                    tempThis.sqliteObj.deleteData(rows[0].row_id, tempThis, tempThis.sendStoredData);
                                                }
                                                break;
                                            case 200003 : {
                                                    logData('SeaLion-Agent Error#440002: Improper ActivityID, deleting from repository');
                                                    tempThis.sqliteObj.deleteDataWithActivityId(rows[0].activityID, tempThis, tempThis.sendStoredData);
                                                }
                                                break;
                                            default : {
                                                    needCheckStoredData = true;
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                case 401 : {
                                        switch(bodyJSON.code) {
                                            case 200004 : {
                                                    logData('SeaLion-Agent Error#440003: Agent not allowed to send data with ActivityID: ' + 
                                                            rows[0].activityID + ', deleting from repository');
                                                    tempThis.sqliteObj.deleteDataWithActivityId(rows[0].activityID, tempThis, tempThis.sendStoredData);
                                                }
                                                break;
                                            case 200001 : {
                                                    needCheckStoredData = true;
                                                    logData('SeaLion-Agent Error#440005: Authentication Failed, Needs reauthentication');
                                                    authenticate.reauthenticate(sessionId);
                                                }
                                                break;
                                            default : {
                                                    needCheckStoredData = true;
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                case 404 : {
                                        switch(bodyJSON.code) {
                                            case 200006:
                                                services.shutDown();
                                                process.nextTick(uninstallSelf);
                                                break;
                                            default : {
                                                    needCheckStoredData = true;
                                                }
                                                break;
                                        }
                                    }
                                    break;
                                case 409 : {

                                        switch(bodyJSON.code) {
                                            case 204011 : {
                                                    logData('SeaLion-Agent Error#440004: Duplicate data. Data deleted from repository');
                                                    tempThis.sqliteObj.deleteData(rows[0].row_id, tempThis, tempThis.sendStoredData);
                                                }
                                                break;
                                            default : {
                                                    needCheckStoredData = true;
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
                    sendOptions = null;
                    toSend = null;
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
                , 'data' : result.output
    };

    this.activityID = result.activityDetails._id;
    
    var path = dataPath + result.activityDetails._id;
    var url = serverOption.sourceURL + path;
    var sessionId = global.sessionCookie;
    var sendOptions = {
          'uri' : url
        , 'json' : toSend
    };
    
    if(sessionId == '') {
        tempThis.handleError(toSend);
        toSend = null;
        result = null;
        sendOptions = null;
        return;
    }
    
    global.request.post(sendOptions, function(err, response, data) {
        
        if(err) {
            tempThis.handleError(toSend);
        } else {
            var bodyJSON = response.body;

            switch(response.statusCode) {
                case 204 : {
                        if(needCheckStoredData) {
                            needCheckStoredData = false;
                            tempThis.sendStoredData();
                            updateConfig();
                            services.startListeningSocketIO();
                        }    
                    }
                    break;
                case 400 : {
                        if(bodyJSON.code) {
                            switch(bodyJSON.code) {
                                case 200002 : {
                                        logData('SeaLion-Agent Error#430001: Payload Missing');
                                        tempThis.handleErroneousData(toSend, tempThis.activityID);
                                    }
                                    break;
                                case 200003 : {
                                        logData('SeaLion-Agent Error#430002: Improper ActivityID, updating config-file');
                                        updateConfig();
                                    }
                                    break;
                                default : {
                                        tempThis.handleError(toSend);
                                    }
                            }
                        } else {
                            tempThis.handleError(toSend);
                        }
                    }
                    break;
                case 401 : {
                        if(bodyJSON.code) {
                            switch(bodyJSON.code) {
                                case 200004 : {
                                        logData('SeaLion-Agent Error#430003: Agent not allowed to send data with ActivityID: ' + result.activityDetails._id + ', updating config-file');
                                        updateConfig();
                                    }
                                    break;
                                case 200001 : {
                                        logData('SeaLion-Agent Error#430005: Authentication Failed, Needs reauthentication');
                                        tempThis.handleError(toSend);
                                        authenticate.reauthenticate(sessionId);
                                    }
                                    break;
                                default : {
                                        tempThis.handleError(toSend);
                                    }
                                    break;
                            }    
                        } else {
                            tempThis.handleError(toSend);
                        }
                    }
                    break;
                case 404 : {
                        switch(bodyJSON.code) {
                          case 200006:
                                services.shutDown();
                                process.nextTick(uninstallSelf);
                            break;
                        }
                    }
                    break;
                case 409 : {
                        logData('SeaLion-Agent Error#430004: Duplicate data. Data dropped');                   
                    }
                    break;
                default: {
                        tempThis.handleError(toSend);
                    }
                    break;
            }
        }
        result = null;
        toSend = null;
        sendOptions = null;
    });
}

module.exports = SendData;