var globals = require('./global.js');
var serverOptions = require('../etc/config/server-config.json').serverDetails;
var removeActivity = require('./execute-services.js').removeActivity;
var addActivity = require('./execute-services.js').addActivity;
var configPath = require('../etc/config/paths-config.json').configPath;

var Sealion = { };
var allowUpdate = true;

var transformBodyJSON = function(bodyJSON, services) { 
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

var isActivityDiff = function(source, target) {
    if(source.command !== target.command) {
        return true;
    }
    
    if(source.interval !== target.interval) {
        return true;
    }
    
    return false;
}

var evaluateServices = function(services) {
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


var updateConfig = function( ) {
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

var handleResponse = function(response) {
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
