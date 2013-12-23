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

var restartAgent = function() {
    var out = fs.openSync('/tmp/sealion_restart.log', 'a');
    var err = fs.openSync('/tmp/sealion_restart.err', 'a');

    delete process.env.__daemon;
    var options = {
        cwd:'/usr/local/sealion-agent'
        , uid: process.getuid()
        , detached: true
        , stdio:['ignore', out, err]
        , env : process.env
    };
    var argumentsArray = [];

    var child = spawn('/usr/local/sealion-agent/etc/restart-agent.sh',
        argumentsArray,
        options);
    child.unref();
}

module.exports = restartAgent;
