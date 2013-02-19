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
            
            var bodyJSON = response.body;            
            if(response.statusCode === 200) {
               cookie = response.headers['set-cookie'];
               var temp = SealionGlobal.request.cookie(cookie[0]); 
               j.add(temp);
               
               // authenticate socket.io
               services.startListeningSocketIO(temp.name + "=" + temp.value);

               // code to update files will come here
               
               SealionGlobal.orgID = bodyJSON.orgID;
               SealionGlobal.agentID = bodyJSON.agentID;
               
               services.startServices(bodyJSON.activities);               
            } else {
                msg = "Status code: " + response.statusCode + " Sealion Agent Error #" + bodyJSON.code + " : " + bodyJSON.message;
                console.log(msg);
            }
        }
    });  
}

authenticate();
