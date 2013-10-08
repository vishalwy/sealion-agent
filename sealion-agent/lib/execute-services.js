/*

 */
/*********************************************

 (c) Webyog, Inc.

 *********************************************/

var ExecuteCommand = require('./execute-command.js');
var Sqlite3 = require('./sqlite-wrapper.js');
var SocketIo = require('./handle-socket-io.js');
var services = require('./global.js').services;
var interId = require('./global.js').interId;
var logData = require('./log.js');

// @const default time interval for command execution 5 mins in ms
var DEFAULT_INTERVAL = 300000;

// Create SQLite connection
var sqliteObj = new Sqlite3();

// Create object to handle SocketIO connection
var socketObj = new SocketIo();

var execArr = [];
var emptySlots = [];
var timeStarted = 0;
var timeDelay = 500;
var msInM = 60000;

function insertInExecArr (activity) {
    if(execArr.length === 0) {
        timeStarted = Date.now();
    }
    var emptySlot = emptySlots.shift();

    if(typeof emptySlot === 'undefined') {
        emptySlot = execArr.length;
        execArr.push(activity['_id']);
    } else {
        execArr[emptySlot] = activity['_id'];
    }

    return emptySlot;
}

// function to handle trigger to execute command
function onExecuteTrigger(activityDetails) {
    // create an object of Execute Command class to execute command
    var ec = new ExecuteCommand(activityDetails, sqliteObj);
    ec.executeCommand({ });
}

function clearActivityInExecArr(activityId) {
    for(var x in execArr) {
        if(execArr[x] === activityId){
            execArr[x] = null;
            emptySlots.push(x);
            break;
        }
    }
}

// function to transform JSON data recieved regarding activities to array of objects for internal purposes
/*
 obj = {
 serviceName: Name of the service e.g. Linux, MySQL
 activityName: Name of the activity e.g. top, iostat
 _id: activity_id
 command: command to be executed under this activity
 interval: interval at which commands have to be executed
 }
 */
function transformServiceJSON(servicesJSON) {
    for(var activity in servicesJSON) {
        var activityDetails = servicesJSON[activity];
        var obj = { };
        obj.serviceName = activityDetails.service;
        obj.activityName = activityDetails.name;
        obj._id = activityDetails._id;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activityDetails._id] = obj;
    }
}

// Function adds activity for executing commands. Used when new activities are to be added or altered
function addActivity(activity) {

    removeActivity(activity);
    logData("Starting activity " + activity['activityName']);
    var index = insertInExecArr(activity);
    var currentTime = Date.now();
    var deltaTime = timeDelay - ((currentTime - timeStarted)%timeDelay);
    var t1 = setTimeout(onExecuteTrigger, deltaTime + timeDelay * index, activity);

    var deltaTimeSchedule = msInM - ((currentTime - timeStarted) % msInM);
    var t2 = setTimeout(function(){
        if(execArr[index] === activity['_id']) {
            interId[activity['_id']] = setInterval(
                onExecuteTrigger,
                activity['interval'] && activity['interval'] <= 604800 ? activity['interval'] * 1000 : DEFAULT_INTERVAL,
                activity
            );

            if((deltaTimeSchedule + timeDelay*index) >= activity['interval'] * 700) {
                onExecuteTrigger(activity);
            }
        } else {
            removeActivity(activity);
        }
    }, deltaTimeSchedule + (timeDelay * index));

    services[activity['_id']] = activity;
}

// Removes activity from executing repeatedly. Used when activities are altered or removed
function removeActivity(activity) {
    if(interId[activity['_id']]) {
        logData("Removing activity " + activity['activityName']);
        clearInterval(interId[activity['_id']]);
        delete(interId[activity['_id']]);
        delete(services[activity['_id']]);
    }

    clearActivityInExecArr(activity['_id']);
}

// starts all activities from JSON recieved at authentication
function startAllActivities(activities) {
    transformServiceJSON(activities);
    lastCommands = 0;
    for(var counter in services) {
        if(services[counter]['activityName'] && services[counter]['command']) {
            addActivity(services[counter]);
        }
    }
}

// stops all activities running
function stopAllActivities() {
    for(var counter in interId) {
        removeActivity(services[counter]);
    }
}

// activates socketIO client to start listening
function startListeningSocketIO() {
    socketObj.createConnection();
}

function joinCatRoom() {
    socketObj.joinCatRoom();
}

// closes socketIO connection
function closeSocketIO() {
    socketObj.closeConnection();
}

// stops all activities, closes SQLite DB connection and SocketIO connection 
function closeAll(){
    stopAllActivities();
    sqliteObj.closeDb();
    closeSocketIO();
}

exports.startServices = startAllActivities;
exports.stopServices = stopAllActivities;
exports.startListeningSocketIO = startListeningSocketIO;
exports.joinCatRoom = joinCatRoom;
exports.closeSocketIO = closeSocketIO;
exports.removeActivity = removeActivity;
exports.addActivity = addActivity;
exports.shutDown = closeAll;