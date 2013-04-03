/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

/*
Application starts with this page
*/

var daemon = require('daemon');
var lockFile = require('./etc/config/lockfile.json').lockFile;
var authenticate = require('./lib/authentication.js').authenticate;
var shutDown = require('./lib/execute-services.js').shutDown;
var fs = require('fs');

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
    console.log('Failed to set uid. ' + err);
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
            console.log('Failed to stop process. ' + err);
            process.exit(1);
        }
    break;

    case "start":
        // check if lock file exists, if yes then exit, as instance already running
        var exist = fs.existsSync(lockFile);
        if(exist){
            console.log('Sealion service already running');
            process.exit(1);
        }
    
        try {
            // start the daemon
            dPID = daemon.start('var/log/sealion.log', 'var/log/sealion.err');
            daemon.lock(lockFile);
            fs.writeFileSync(lockFile, dPID.toString(), 'utf8');
        } catch(err) {
            console.log('Failed to start service. ' + err);
            process.exit(1);
        }    
    break;

    default:
        console.log('Usage: [start|stop]');
        process.exit(0);
    break;
}


// Handle message SIGTERM
process.on('SIGTERM', function() {
    shutDown();
    console.log('SIGTERM: services closed');
    process.exit(0);        
});

// Handle message SIGINT
process.on('SIGINT', function() {
    shutDown();
    console.log('SIGINT: services closed');        
    process.exit(0);
});

// After initial file setups and starting daemon check for authentication
authenticate();
