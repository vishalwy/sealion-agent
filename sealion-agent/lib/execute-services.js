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

var timeDelay = 500;

var executionQue = [];
var execQueIntervalId = null;

function insertInExecQue (activity) {
    executionQue.push(activity._id);
    if( ! execQueIntervalId ) {
        execQueIntervalId = setInterval( executeScheduledCommand, timeDelay);
    }
}

function executeScheduledCommand() {
    var activityId = executionQue.shift();
    if(activityId){
        var activity = services[activityId];
        activity && onExecuteTrigger(activity);
    } else {
        if(execQueIntervalId) {
            clearInterval(execQueIntervalId);
            execQueIntervalId = null;
        }
    }
}

// function to handle trigger to execute command
function onExecuteTrigger(activityDetails) {
    // create an object of Execute Command class to execute command
    var ec = new ExecuteCommand(activityDetails, sqliteObj);
    ec.executeCommand({ });
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
function transformServiceJSON(bodyJSON, lServices) {
    for(var activity in bodyJSON) {
        var activityDetails = bodyJSON[activity];
        var obj = new Object();
        obj.serviceName = activityDetails.service;
        obj.activityName = activityDetails.name;
        obj._id = activityDetails._id;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        lServices[activityDetails._id] = obj;
    }
}

// Function adds activity for executing commands. Used when new activities are to be added or altered
function addActivity(activity) {

    removeActivity(activity);
    logData("Starting activity " + activity['activityName']);
    insertInExecQue(activity);

    interId[activity['_id']] = setInterval(
        insertInExecQue,
        activity['interval'] && activity['interval'] <= 604800 ? activity['interval'] * 1000 : DEFAULT_INTERVAL,
        activity
    );

    services[activity['_id']] = activity;
}

// Removes activity from executing repeatedly. Used when activities are altered or removed
function removeActivity(activity) {
    if(interId[activity['_id']]) {
        logData("Removing activity " + activity['activityName']);
        showedMsg = true;
        clearInterval(interId[activity['_id']]);
        delete(interId[activity['_id']]);
        delete(services[activity['_id']]);
    }
}

// starts all activities from JSON recieved at authentication
function startAllActivities(activities) {
    var lServices = {};
    transformServiceJSON(activities, lServices);
    for(var counter in lServices) {
        if(lServices[counter]['activityName'] && lServices[counter]['command']) {
            addActivity(lServices[counter]);
        }
    }
}

// stops all activities running
function stopAllActivities() {
    for(var counter in services) {
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