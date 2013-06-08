/*
Module is written to authenticate Sealion agent with server.
Module also handles reauthentication
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var fs = require('fs');
var options = require('../etc/config/server-config.json').serverDetails;
var services = require('./execute-services.js');
var SealionGlobal = require('./global.js');
var authPath = require('../etc/config/paths-config.json').agentAuth;
var lockFile = require('../etc/config/lockfile.json').lockFile;
var logData = require('./log.js');
var updateAgent = require('./update-agent.js');

SealionGlobal.request = require('request');

var attemptNumber = 0;
var allowAuth = true;

// function deletes lock file
function cleanUp() {
    fs.unlinkSync(lockFile);
}

// sends suthentication request
function sendAuthRequest() {
    
    var agentDetails= { };
    var msg ='';
    
    // check if agent-token is present or not
    // if not then close the program with error message 
    try{
        agentDetails.agentToken = require('../etc/config/agent-config.json').agentToken;
    } catch (err) {
        logData('Sealion-Agent Error#410001: Agent-token missing or can not be read');
        logData('Bye!!! Terminating service');
        cleanUp();
        process.exit(1);
    }

    var url = options.sourceURL + authPath;
    var sendOptions = {
          'uri' : url
        , 'json' : agentDetails
    };
    
    // Send authentication request      
    SealionGlobal.request.post( sendOptions , function(err, response, data) {
        allowAuth = true;
        if(err) {
            logData('Sealion-Agent Error#420001: Unable to create connection, attempting to reconnect');
            
            /*
            if maxConnectAttempts is less than 0 that means we need to continously
            attempt authentication every 5 mins.
            if array is defined with time-intervals after which to attempt connections then
            use that array.
            If max connection attempts reachedd then try making connection again after 
            every last index value seconds
            */
            
            if(options.maxConnectAttempts < 0) {
                setTimeout(authenticate, 300000);
            } else if(attemptNumber >= (options.reconnectInterval.length - 1)) {
                setTimeout(authenticate, 
                    options.reconnectInterval[options.reconnectInterval.length - 1] * 1000);
            } else {
                setTimeout(authenticate, 
                    options.reconnectInterval[attemptNumber] * 1000);
            }
        } else {
            var bodyJSON = response.body;            
            switch(response.statusCode) {
                case 200: {
                        var cookie = response.headers['set-cookie'];
                        var temp = SealionGlobal.request.cookie(cookie[0]); 
                        attemptNumber = 0;

                        SealionGlobal.sessionCookie = temp.name + "=" + temp.value;
                        SealionGlobal.agentId = bodyJSON._id;
                        SealionGlobal.orgId = bodyJSON.org;
                        SealionGlobal.categoryId = bodyJSON.category;
                        
                        var agentVersion = require('../etc/config/agent-config.json').agentVersion;
                        
                        if(agentVersion != bodyJSON.agentVersion) {
                            logData('updating to agent-version on startup: ' + bodyJSON.agentVersion)
                            services.shutDown();
                            updateAgent(bodyJSON.agentVersion);
                            process.exit(0);
                        }
 
                        services.startListeningSocketIO();
                        
                        services.startServices(bodyJSON.activities);
                    }
                    break;
                case 400: {
                        logData('Sealion-Agent Error#410003: Bad request, agent-token missing in request');
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;
                case 401: {
                        logData('Sealion-Agent Error#410002: Invalid Agent-token');
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;    
                default: {
                        msg = "Status code: " + response.statusCode + 
                                " Sealion Agent Error #" + bodyJSON.code + " : " + bodyJSON.message;
                        logData(msg);
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;
            }
        }
    });
}


// function to initiate authentication process
function authenticate() {
    /* check for maxConnectAttempts limit, if it is less than
        0 then attempt authenticating every 5 mins
        else check for number of attempts made
    */
    if(options.maxConnectAttempts < 0) {
        sendAuthRequest();    
    } else if(attemptNumber < options.maxConnectAttempts){ 
        attemptNumber++;
        sendAuthRequest();
    } else {
        logData('Sealion-Agent Error#410004: Max Recconect attempts exceeded. Unable to reconnect');
        logData('Bye!!! Terminating service');
        cleanUp();
        process.exit(1);    
    }
}

// function to re-authenticate Sealion agent
function reauthenticate(ssId) {
    if(allowAuth && ssId == SealionGlobal.sessionCookie) {
        allowAuth = false;
        SealionGlobal.sessionCookie='';
        services.stopServices();
        process.nextTick( function() {
            authenticate();
        });
    }
}

exports.authenticate = authenticate;
exports.reauthenticate = reauthenticate;