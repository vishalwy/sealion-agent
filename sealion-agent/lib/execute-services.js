var ExecuteCommand = require('./execute-command.js');
var Sqlite3 = require('./sqlite-wrapper.js');
var SocketIo = require('./handle-socket-io.js');
var services = require('./global.js').services;
var interId = require('./global.js').interId;

var Sealion = { };
    
Sealion.DEFAULT_INTERVAL = 300000;

var sqliteObj = new Sqlite3();
var socketObj = new SocketIo();

Sealion.onExecuteTrigger = function(activityDetails) {
    var ec = new ExecuteCommand(activityDetails, sqliteObj);
    ec.executeCommand({ });
}

Sealion.transformServiceJSON = function(servicesJSON) {
    for(var activity in servicesJSON) {
        var activityDetails = servicesJSON[activity];
        var obj = { };
        obj.serviceName = activityDetails.serviceName;
        obj.activityName = activityDetails.activityName;
        obj._id = activity;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activity] = obj;
    }
}

var addActivity = function(activity) {
    console.log("adding activity" + activity['_id']);
    removeActivity(activity);
    interId[activity['_id']] = setInterval(
        Sealion.onExecuteTrigger,
        activity['interval'] ? activity['interval'] * 1000 : Sealion.DEFAULT_INTERVAL, 
        activity 
    );
    services[activity['_id']] = activity;
}

var removeActivity = function(activity) {
    console.log("removing activity" + activity['_id']);
    if(interId[activity['_id']]) {
        clearInterval(interId[activity['_id']]);
        delete(services[activity['_id']])
    }
}

var startAllActivities = function(activities) {
    Sealion.transformServiceJSON(activities);
    
    for(var counter in services) {
        if(services[counter]['activityName'] && services[counter]['command']) {
            console.log("starting service for " + services[counter]['activityName']);
            
            interId[services[counter]['_id']] = setInterval(
                    Sealion.onExecuteTrigger, 
                    services[counter]['interval'] ? services[counter]['interval'] * 1000 : Sealion.DEFAULT_INTERVAL, 
                    services[counter]                    
                );
        }
    }
}

var stopAllActivities = function() {
    for(var counter in interId) {
        clearInterval(interId[counter]);
    }
    sqliteObj.closeDb();
    socketObj.closeConnection();
}

var startListeningSocketIO = function(cookieData) {
    socketObj.createConnection(cookieData); 
}

var closeSocketIO = function() {
    socketObj.closeConnection();
}

exports.startServices = startAllActivities;
exports.stopServices = stopAllActivities;
exports.startListeningSocketIO = startListeningSocketIO;
exports.closeSocketIO = closeSocketIO;
exports.removeActivity = removeActivity;
exports.addActivity = addActivity;
