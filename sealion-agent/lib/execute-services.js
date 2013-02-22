var ExecuteCommand = require('./execute-command.js');
var Sqlite3 = require('./sqlite-wrapper.js');
var SocketIo = require('./handle-socket-io.js');
var global = require('./global.js');

var services = [ ];
var Sealion = { };
    
Sealion.DEFAULT_INTERVAL = 300000;

var sqliteObj = new Sqlite3();
var socketObj = new SocketIo();

Sealion.onExecuteTrigger = function(activityDetails) { 
    var ec = new ExecuteCommand(activityDetails, sqliteObj);
    ec.executeCommand({ });
}

Sealion.interId = [ ];

Sealion.transformServiceJSON = function(servicesJSON) {
    for(var activity in servicesJSON) {
        var activityDetails = servicesJSON[activity];
        var obj = new Object();
        obj.serviceName = activityDetails.serviceName;
        obj.activityName = activityDetails.activityName;
        obj._id = activity;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activity] = obj;
    }
}

var startServices = function(activities) {
    Sealion.transformServiceJSON(activities);
    
    for(var counter in services) {
        if(services[counter]['activityName'] && services[counter]['command']) {
            console.log("starting service for " + services[counter]['activityName']);
            Sealion.interId.push(
                setInterval(
                    Sealion.onExecuteTrigger, 
                    /*services[counter]['interval'] ? services[counter]['interval'] * 1000 : Sealion.DEFAULT_INTERVAL*/ 1000, 
                    services[counter]                    
                )
            );
        }
    }
}

var stopServices = function() {
    console.log("Stopping Services");
    for(var counter in Sealion.interId) {
        clearInterval(Sealion.interId[counter]);
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

exports.startServices = startServices;
exports.stopServices = stopServices;
exports.startListeningSocketIO = startListeningSocketIO;
exports.closeSocketIO = closeSocketIO;
