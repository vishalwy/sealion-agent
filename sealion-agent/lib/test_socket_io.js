var fs = require('fs');
var options = require('../etc/config/server-config.json').serverDetails;
var services = require('./execute-services.js');
var SealionGlobal = require('./global.js');
var cookie = { };

SealionGlobal.request = require('request');

var j = SealionGlobal.request.jar();
SealionGlobal.request = SealionGlobal.request.defaults({jar:j});

function authenticate() {
    var agentDetails= { };
    var msg ='';
    
    try{
        agentDetails.agentToken = require('../etc/config/agent-config.json').agentToken;
    } catch (err) {
        console.log("Sealion-Agent Error#400007: Terminating Process due to invaild/absence of agent token");
        process.exit(400007);
    }

    options.path += 'sessions/agents';
    
    var url = options.sourceURL + options.path;
    var sendOptions = {
          'uri' : url
        , 'json' : agentDetails
    };
    SealionGlobal.request.post( sendOptions , function(err, response, data) {
        if(err) {
            console.log(err);
        } else {
            
            // authenticate socket.io - client
            
            
            var bodyJSON = response.body;            
            if(response.statusCode === 200) {
                
               cookie = response.headers['set-cookie'];
               var temp = SealionGlobal.request.cookie(cookie[0]); 
               j.add(temp);
               
               console.log(temp.name + "=" + temp.value);
               
               authenticateSocketIO(temp.name + "=" + temp.value);
               
               // code to update files will come here
               
               SealionGlobal.orgID = bodyJSON.orgID;
               SealionGlobal.agentID = bodyJSON.agentID;
               
            } else {
                msg = "Status code: " + response.statusCode + " Sealion Agent Error #" + bodyJSON.code + " : " + bodyJSON.message;
                console.log(msg);
            }
        }
    });  
}

var io = require('socket.io-client');
var socketIoOptions = require('../etc/config/socket-io-config.js');

function authenticateSocketIO(cookie) {
    var socket = io.connect('https://rituparna.webyog.com:8888',{'cookies':cookie});
    
    socket.on('connecting', function(something) {
        console.log(something);
    });

    socket.on('disconnect', function() {
        console.log("Server gone away");
    });
    
    socket.on('connect', function() {
        console.log("connected");
    });

    socket.on('I am the king of the world', function(msg) {
        console.log(msg);
    });
    
    socket.on('update', function(msg) {
        console.log('Got message ' + JSON.stringify(msg));
    });

    socket.on('error', function(error) {
        console.log("Error in connection" + error);
    });
}

authenticate();
