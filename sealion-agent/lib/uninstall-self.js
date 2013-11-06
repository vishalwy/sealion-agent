/*
 module to initiate updating agent.
 It will initiate update script in /usr/local/sealion-agent/update.sh and exit

 */

/*********************************************

 (c) Webyog, Inc.

 *********************************************/

var spawn = require('child_process').spawn;
var fs = require('fs');

var uninstallAgent = function() {
    var out = fs.openSync('/tmp/sealion_uninstall.log', 'a');
    var err = fs.openSync('/tmp/sealion_uninstall.err', 'a');
    var options ={
        cwd:'/usr/local/sealion-agent'
        , uid: process.getuid()
        , detached: true
        , stdio:['ignore', out, err]
    };

    var child = spawn('/usr/local/sealion-agent/uninstall.sh', ['-u'], options);
    child.unref();
}

module.exports = uninstallAgent;