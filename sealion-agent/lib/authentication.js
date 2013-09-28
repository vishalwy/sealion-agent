/*
Module is written to authenticate Sealion agent with server.
Module also handles reauthentication
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>
 (c) Webyog Inc.

*********************************************/

function testURL(str) {
    return typeof str === 'string' && str.length < 2083 && str.match(/^(?!mailto:)(?:(?:https?|ftp):\/\/)?(?:\S+(?::\S*)?@)?(?:(?:(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}(?:\.(?:[0-9]\d?|1\d\d|2[0-4]\d|25[0-4]))|(?:(?:[a-z\u00a1-\uffff0-9]+-?)*[a-z\u00a1-\uffff0-9]+)(?:\.(?:[a-z\u00a1-\uffff0-9]+-?)*[a-z\u00a1-\uffff0-9]+)*(?:\.(?:[a-z\u00a1-\uffff]{2,})))|localhost)(?::\d{2,5})?(?:\/[^\s]*)?$/i);
}


var SealionGlobal = require('./global.js');
var url = require('url');
var fs = require('fs');
var proxy;

if(fs.existsSync('/usr/local/sealion-agent/etc/config/proxy.json')) {
    proxy = require('../etc/config/proxy.json');

    if( proxy.http_proxy && proxy.http_proxy.length && testURL(proxy.http_proxy)) {
        SealionGlobal.http_proxy= proxy.http_proxy.substring(0,4) === 'http' ? proxy.http_proxy : 'http://' + proxy.http_proxy;
        var curlrcPath = '/usr/local/sealion-agent/.curlrc';
        if(! fs.existsSync(curlrcPath)) {
            fs.writeFileSync(curlrcPath, 'proxy = ' + proxy.http_proxy);
        }
    }
}

var config = require('../etc/config/sealion-config.json');
var options = config.serverDetails;
var services = require('./execute-services.js');
var authPath = config.agentAuth;
var lockFile = config.lockFile;
var logData = require('./log.js');
var updateAgent = require('./update-agent.js');

if(SealionGlobal.http_proxy && SealionGlobal.http_proxy.length) {
    SealionGlobal.request = require('request').defaults({proxy : SealionGlobal.http_proxy});
} else {
    SealionGlobal.request = require('request');
}



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
    var agentId;
    var agentConfig;
    // check if agent-token is present or not
    // if not then close the program with error message 
    try{
        agentConfig = require('../etc/config/agent-config.json');
        agentDetails.orgToken = agentConfig.orgToken;
        agentId = agentConfig.agentId;
    } catch (err) {
        logData('SeaLion-Agent Error#410001: Authentication details missing or can not be read');
        logData('Bye!!! Terminating service');
        cleanUp();
        process.exit(1);
    }

    var url = options.sourceURL + authPath.replace('<agent-id>', agentId);
    var sendOptions = {
          'uri' : url
        , 'json' : agentDetails
    };
    
    // Send authentication request      
    SealionGlobal.request.post( sendOptions , function(err, response, data) {
        allowAuth = true;
        if(err) {
            logData('SeaLion-Agent Error#420001: Unable to create connection, attempting to reconnect');
            
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
                        
                        var agentVersion = agentConfig.agentVersion;
                        
                        if(agentVersion != bodyJSON.agentVersion) {
                            logData('SeaLion Agent is updating to agent-version on startup: ' + bodyJSON.agentVersion)
                            services.shutDown();
                            updateAgent(bodyJSON.agentVersion);
                            process.exit(0);
                        }
 
                        services.startListeningSocketIO();
                        services.startServices(bodyJSON.activities);
                    }
                    break;
                case 400: {
                        logData('SeaLion-Agent Error#410003: Bad request, agent-id missing in request');
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;
                case 401:
                    {
                        logData('SeaLion-Agent Error#410002: Invalid organization-token');
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;
                case 404:
                    {
                        logData('SeaLion-Agent Error#410002: Agent not found');
                        logData('Bye!!! Terminating service');
                        cleanUp();
                        process.exit(1);
                    }
                    break;    
                default: {
                        msg = "Status code: " + response.statusCode + 
                                " SeaLion Agent Error #" + bodyJSON.code + " : " + bodyJSON.message;
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
        logData('SeaLion-Agent Error#410004: Max Recconect attempts exceeded. Unable to reconnect');
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
        //services.closeSocketIO();
        process.nextTick( function() {
            authenticate();
        });
    }
}

exports.authenticate = authenticate;
exports.reauthenticate = reauthenticate;