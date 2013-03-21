var ExecuteCommand = require('./execute-command.js');
var Sqlite3 = require('./sqlite-wrapper.js');
var SocketIo = require('./handle-socket-io.js');
var SendData = require('./send-data.js');
var services = require('./global.js').services;
var interId = require('./global.js').interId;

var DEFAULT_INTERVAL = 300000;

var sqliteObj = new Sqlite3();
var socketObj = new SocketIo();

function onExecuteTrigger(activityDetails) {
    var ec = new ExecuteCommand(activityDetails, sqliteObj);
    ec.executeCommand({ });
}

function transformServiceJSON(servicesJSON) {
    for(var activity in servicesJSON) {
        var activityDetails = servicesJSON[activity];
        var obj = { };
        obj.serviceName = activityDetails.serviceName;
        obj.activityName = activityDetails.activityName;
        obj._id = activityDetails._id;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activityDetails._id] = obj;
    }
}

function addActivity(activity) {
    console.log("adding activity" + activity['_id']);
    removeActivity(activity);
    interId[activity['_id']] = setInterval(
        onExecuteTrigger,
        activity['interval'] ? activity['interval'] * 1000 : DEFAULT_INTERVAL, 
        activity 
    );
    services[activity['_id']] = activity;
}

function removeActivity(activity) {
    console.log("removing activity" + activity['_id']);
    if(interId[activity['_id']]) {
        clearInterval(interId[activity['_id']]);
        delete(services[activity['_id']])
    }
}

function startAllActivities(activities) {
    transformServiceJSON(activities);
    
    for(var counter in services) {
        if(services[counter]['activityName'] && services[counter]['command']) {
            console.log('starting service for ' + services[counter]['activityName']);
            
            interId[services[counter]['_id']] = setInterval(
                    onExecuteTrigger, 
                    services[counter]['interval'] ? services[counter]['interval'] * 1000 : DEFAULT_INTERVAL, 
                    services[counter]                    
                );
        }
    }
    
    var sendData = new SendData(sqliteObj);
    sendData.sendStoredData();
}

function stopAllActivities() {
    for(var counter in interId) {
        console.log('stopping service for ' + services[counter]['activityName']);
        clearInterval(interId[counter]);
    }
}

function startListeningSocketIO(cookieData) {
    socketObj.createConnection(cookieData); 
}

function closeSocketIO() {
    socketObj.closeConnection();
}

function closeAll(){
    stopAllActivities();
    sqliteObj.closeDb();
    closeSocketIO();
}

exports.startServices = startAllActivities;
exports.stopServices = stopAllActivities;
exports.startListeningSocketIO = startListeningSocketIO;
exports.closeSocketIO = closeSocketIO;
exports.removeActivity = removeActivity;
exports.addActivity = addActivity;
exports.shutDown = closeAll;
