var serverOption = require('../etc/config/server-config.json').serverDetails;
var Sqlite3 = require('./sqlite-wrapper.js');
var global = require('./global.js');

var Sealion = { };
var needCheckStoredData = true;


Sealion.SendData = function (sqliteObj) {
    this.dataToInsert = '';
    this.sqliteObj = sqliteObj;
    this.activityID = '';
};

Sealion.SendData.prototype.handleError = function() {
    this.sqliteObj.insertData(this.dataToInsert, this.activityID);
    needCheckStoredData = true;
}

Sealion.SendData.prototype.sendStoredData = function() {
    var sobj = new Sqlite3();
    var db = sobj.getDb();
    var tempThis = this;
    
    if(db) {
        db.all('SELECT row_id, activityID, date_time, result FROM repository LIMIT 0,1', function(error, rows) {
            
            if(error) {
                needCheckStoredData = true;
                console.log("error in retreiving data");
            } else {
                if(rows.length > 0) {
                    console.log(rows[0].row_id);
                    
                    var path = '/data/' + global.orgID + '/' + global.agentID + '/' + rows[0].activityID;
                    var url = serverOption.sourceURL + path;
                    var toSend = JSON.parse(rows[0].result);
                    
                    var sendOptions = {
                          'uri' : url
                        , 'json' : toSend
                    };
                    
                    global.request.post(sendOptions, function(err, response, data) {
                        if(err) {
                            needCheckStoredData = true;
                            console.log("Error in Sending stored data");
                        } else {
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

Sealion.SendData.prototype.dataSend = function (result) {
    var tempThis = this;
    
    var toSend = {'returnCode' : result.code
                , 'timestamp' : result.timeStamp
                , 'data' : result.output };
                
    this.dataToInsert = JSON.stringify(toSend);
    this.activityID = result.activityDetails._id;
    
    
    var path = '/data/' + global.orgID + '/' + global.agentID + '/' + result.activityDetails._id;
    var url = serverOption.sourceURL + path;
    var sendOptions = {
          'uri' : url
        , 'json' : toSend
    };
    
    global.request.post(sendOptions, function(err, response, data) {
        response.on('error', function(error) {
            tempThis.handleError();
        });
        
        response.on('uncaughtException', function(error) {
            tempThis.handleError();
        });
        
        if(err) {
            tempThis.handleError();
        } else {
            if(response.statusCode === 200) {
                if(needCheckStoredData) {
                    needCheckStoredData = false;
                    tempThis.sendStoredData();
                }
            } else {
                tempThis.handleError();
            }
        }
    });
}

module.exports = Sealion.SendData;
