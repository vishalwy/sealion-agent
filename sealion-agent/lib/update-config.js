/* 
Module updates changed activities at run time
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var globals = require('./global.js');
var serverOptions = require('../etc/config/server-config.json').serverDetails;
var removeActivity = require('./execute-services.js').removeActivity;
var addActivity = require('./execute-services.js').addActivity;
var configPath = require('../etc/config/paths-config.json').configPath;

var allowUpdate = true;

// transforms activity JSON recieved to an associative array of objects for internal use
function transformBodyJSON(bodyJSON, services) { 
    for(var activity in bodyJSON) {
        var activityDetails = bodyJSON[activity];
        var obj = new Object();
        obj.serviceName = activityDetails.serviceName;
        obj.activityName = activityDetails.activityName;
        obj._id = activity;
        obj.command = activityDetails.command;
        obj.interval = activityDetails.interval;

        services[activity] = obj;
    }
}

// check if activity differs in command or interval
function isActivityDiff(source, target) {
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
               addActivity(services[activityId]);
            }   
        } else {
            addActivity(services[activityId]);
        }
    }
    
    for(var activityId in globals.services) {
        if(! services[activityId]) {
            removeActivity(globals.services[activityId]);
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
                console.log('Error in retreving config file');
            } else {
                handleResponse(response);     
            }
        });
    }
}

// callback function to handle response
function handleResponse(response) {
    var bodyJSON = response.body;
    var services = { };
    switch(response.statusCode) {
        case 200: {
                transformBodyJSON(bodyJSON.activities, services);
                evaluateServices(services);
            }
            break;
    }
}

module.exports = updateConfig;
