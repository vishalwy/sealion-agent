/*
Module is class representation of oject used to execute commands
*/

/*********************************************

Author: Shubhansh

*********************************************/
var Result = require('./result.js');
var exec = require ('child_process').exec;
var SendData = require('./send-data.js');
var global = require('./global.js');

/** @constructor to execute command class*/
var ExecuteCommand = function(activityDetails, sqliteObj) {
    this.result = new Result();
    this.result.activityDetails = activityDetails;
    this.sqliteObj = sqliteObj;
};

// handles command execution output and initiates sending process
ExecuteCommand.prototype.handleCommandOutput = function () {
    // create object to send data for this command
    var sendData = new SendData(this.sqliteObj);
    sendData.dataSend(this.result);
};

// function to process command execution output
ExecuteCommand.prototype.processCommandResult = function (error, stdout, stderr) {
    
    var tempThis = this;

    if(error) {
        this.result.code = error.code;
        this.result.output = stderr !== '' ? stderr : stdout;
    } else {
        this.result.output = stdout !== '' ? stdout : stderr;
    }

    process.nextTick( function () {
        tempThis.handleCommandOutput();
    });
};

// function executes command
ExecuteCommand.prototype.executeCommand = function(options) {

    var tempThis = this;
    
    this.result.options = options;
    this.result.timeStamp = new Date().getTime();

    var child = exec(this.result.activityDetails.command, { }, function(error, stdout, stderr){
        tempThis.processCommandResult(error, stdout, stderr);
    });
};

module.exports = ExecuteCommand;