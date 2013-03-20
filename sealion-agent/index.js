var daemon = require('daemon');
var lockFile = require('./etc/config/lockfile.json').lockFile;
var authenticate = require('./lib/authentication.js').authenticate;
var shutDown = require('./lib/execute-services.js').shutDown;
var fs = require('fs');

var args = process.argv;
var dPID;

if (process.getuid && process.setuid) {
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
            process.kill(parseInt(fs.readFileSync(lockFile)));
            fs.unlinkSync(lockFile);
            process.exit(0);
        } catch (err) {
            console.log('Failed to stop process. ' + err);
            process.exit(1);
        }
    break;

    case "start":
        try {
            dPID = daemon.start('/tmp/sealion.log', '/tmp/sealion.err');
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

process.on('SIGTERM', function() {
    shutDown();
    console.log('SIGTERM: services closed');
    process.exit(0);        
});

process.on('SIGINT', function() {
    shutDown();
    console.log('SIGINT: services closed');        
    process.exit(0);
});

authenticate();
