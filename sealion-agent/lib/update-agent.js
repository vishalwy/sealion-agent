/* 
module to initiate updating agent.
It will initiate update script in /usr/local/sealion-agent/update.sh and exit

*/

/*********************************************

 (c) Webyog, Inc.
 Author: Shubhansh Varshney <shubhansh.varshney@webyog.com>

*********************************************/

var spawn = require('child_process').spawn;
var fs = require('fs');
var agentDetails = require('../etc/config/agent-config.json');
var SealionGlobal = require('./global.js');

var updateAgent = function(version) {
    var out = fs.openSync('/tmp/sealion_update.log', 'a');
    var err = fs.openSync('/tmp/sealion_update.err', 'a');

    delete process.env.__daemon;

    var options ={
          cwd:'/usr/local/sealion-agent'
        , uid: process.getuid()
        , detached: true
        , stdio:['ignore', out, err]
        , env : process.env
    };
    var argumentsArray = ['-a', agentDetails.agentId, '-v', version, '-o', agentDetails.orgToken];

    if(SealionGlobal.http_proxy && SealionGlobal.http_proxy.length) {
        argumentsArray.push('-x', SealionGlobal.http_proxy);
    }

    var child = spawn('/usr/local/sealion-agent/etc/update.sh', 
        argumentsArray,
        options);
    child.unref();
}

module.exports = updateAgent;
