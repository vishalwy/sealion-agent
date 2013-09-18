/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

/*
Application starts with this page
*/

var daemon = require('daemon');
var lockFile = require('./etc/config/sealion-config.json').lockFile;
var authenticate = require('./lib/authentication.js').authenticate;
var shutDown = require('./lib/execute-services.js').shutDown;
var fs = require('fs');
var logData = require('./lib/log.js');



var args = process.argv;
var dPID;

/*
Check if setuid function is present. Check is done so that process can be owned
by user 'sealion'. This enables all functions be performed by user 'sealion'.
In case of failure leave exit the program with error message
*/
if (process.setuid) {
  try {
    process.setuid('sealion');
  } catch (err) {
    logData('Failed to set uid. ' + err);
    process.exit(1);
  }
}

switch(args[2]) {
    case "stop":
        try {
            // Close the running instance
            process.kill(parseInt(fs.readFileSync(lockFile)));
            
            //delete lock file
            fs.unlinkSync(lockFile);
            process.exit(0);
        } catch (err) {
            logData('Failed to stop process. ' + err);
            process.exit(1);
        }
    break;

    case "start":
        // check if lock file exists, if yes then exit, as instance already running
        var exist = fs.existsSync(lockFile);
        if(exist){
            logData('Sealion service already running');
            process.exit(1);
        }
    
        try {
            // start the daemon
            dPID = daemon.start('var/log/sealion.log', 'var/log/sealion.err');
            daemon.lock(lockFile);
            fs.writeFileSync(lockFile, dPID.toString(), 'utf8');
        } catch(err) {
            logData('Failed to start service. ' + err);
            process.exit(1);
        }    
    break;

    default:
        logData('Usage: [start|stop]');
        process.exit(0);
    break;
}


// Handle message SIGTERM
process.on('SIGTERM', function() {
    shutDown();
    logData('SIGTERM: services closed');
    process.exit(0);        
});

// Handle message SIGINT
process.on('SIGINT', function() {
    shutDown();
    logData('SIGINT: services closed');        
    process.exit(0);
});

logData('Sealion-Agent: service started');

fs.chmod('/usr/local/sealion-agent/var/log/sealion.log', 644, function(err){
    if(err){
        logData('Unable to change ownership of sealion.log');
    }
});

fs.chmod('/usr/local/sealion-agent/var/log/sealion.err', 644, function(err){
    if(err){
        logData('Unable to change ownership of sealion.err');
    }

});

// After initial file setups and starting daemon check for authentication
authenticate();