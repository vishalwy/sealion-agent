/* 
Module updates changed activities at run time
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var globals = require('./global.js');
var config = require('../etc/config/sealion-config.json');
var serverOptions = config.serverDetails;
var executeServices = require('./execute-services.js');
var configPath = config.configPath;
var logData = require('./log.js');
var allowUpdate = true;

// transforms activity JSON recieved to an associative array of objects for internal use
function transformBodyJSON(bodyJSON, services) { 
    for(var activity in bodyJSON) {
        var activityDetails = bodyJSON[activity];
        var obj = new Object();
        obj.serviceName = activityDetails.service;
        obj.activityName = activityDetails.name;
        obj._id = activityDetails._id;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activityDetails._id] = obj;
    }
}

// check if activity differs in command or interval
function isActivityDiff(source, target) {

    if(source.activityName !== target.activityName) {
        source.activityName = target.activityName;
    }

    if(source.command !== target.command) {
        return true;
    }
    
    if(source.interval !== target.interval) {
        return true;
    }
    
    return false;
}

/*
function evaluate services for adding or removing
*/
function evaluateServices(services) {
    for(var activityId in services) {
        if(globals.services[activityId]) {
            if(isActivityDiff(globals.services[activityId], services[activityId])) {
               executeServices.addActivity(services[activityId]);
            }   
        } else {
            executeServices.addActivity(services[activityId]);
        }
    }
    
    for(var activityId in globals.services) {
        if(globals.services[activityId] && ! services[activityId]) {
            executeServices.removeActivity(globals.services[activityId]);
        }
    }
}

// function to initiate update activity details
function updateConfig( ) {
    var self = this;
    var url = serverOptions.sourceURL + configPath;
    
    var options = {
          'uri' : url
        , 'json' : { } 
    };

    if(allowUpdate) {
        allowUpdate = false;
        globals.request.get(options, function(err, response, data){
            allowUpdate = true;
            if(err) {
                logData('Error in retreving config data');
            } else {
                handleResponse(response);     
            }
        });
    }
}

// function to handle response
function handleResponse(response) {
    var bodyJSON = response.body;
    var services = { };

    switch(response.statusCode) {
        case 200: {
                logData('Fetched activity details');
                transformBodyJSON(bodyJSON.activities, services);
                evaluateServices(services);

                if(globals.categoryId !== bodyJSON.category) {
                    globals.categoryId = bodyJSON.category;
                    executeServices.joinCatRoom();
                }

            }
            break;
    }
}

module.exports = updateConfig;
