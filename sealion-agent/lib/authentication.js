var fs = require('fs');
var options = require('../etc/config/server-config.json').serverDetails;
var services = require('./execute-services.js');
var SealionGlobal = require('./global.js');
var cookie = { };

SealionGlobal.request = require('request');

var attemptNumber = 0;
var j = SealionGlobal.request.jar();
SealionGlobal.request = SealionGlobal.request.defaults({jar:j});

function sendAuthRequest() {
    var agentDetails= { };
    var msg ='';
    
    try{
        agentDetails.agentToken = require('../etc/config/agent-config.json').agentToken;
    } catch (err) {
        console.log('Sealion-Agent Error#410001: Agent-token missing or can not be read');
        console.log('Bye!!! Terminating service');
        process.exit(1);
    }

    options.path = '/sessions/agents';

    var url = options.sourceURL + options.path;
    var sendOptions = {
          'uri' : url
        , 'json' : agentDetails
    };
    
    SealionGlobal.request.post( sendOptions , function(err, response, data) {
        if(err) {
            console.log('Sealion-Agent Error#420001: Unable to create connection, attempting to reconnect');
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
                        cookie = response.headers['set-cookie'];
                        var temp = SealionGlobal.request.cookie(cookie[0]); 
                        j.add(temp);
                        
                        services.startListeningSocketIO(temp.name + "=" + temp.value);
                        
                            // code to update files will come here
               
                        //SealionGlobal.orgID = bodyJSON.orgID;
                        //SealionGlobal.agentID = bodyJSON.agentID;
               
                        services.startServices(bodyJSON.activities);
                    }
                    break;
                case 400: {
                        console.log('Sealion-Agent Error#410003: Bad request, agent-token missing in request');
                        console.log('Bye!!! Terminating service');
                        process.exit(1);
                    }
                    break;
                case 401: {
                        console.log('Sealion-Agent Error#410002: Invalid Agent-token');
                        console.log('Bye!!! Terminating service');
                        process.exit(1);
                    }
                    break;    
                default: {
                        msg = "Status code: " + response.statusCode + 
                                " Sealion Agent Error #" + bodyJSON.code + " : " + bodyJSON.message;
                        console.log(msg);
                        console.log('Bye!!! Terminating service');
                        process.exit(1);
                    }
                    break;
            }
        }
    });
}

function authenticate() {
    if(options.maxConnectAttempts < 0) {
        sendAuthRequest();    
    } else if(attemptNumber < options.maxConnectAttempts){ 
        attemptNumber++;
        sendAuthRequest();
    } else {
        console.log('Sealion-Agent Error#410004: Max Recconect attempts exceeded. Unable to reconnect');
        console.log('Bye!!! Terminating service');
        process.exit(1);    
    }
}

authenticate();
