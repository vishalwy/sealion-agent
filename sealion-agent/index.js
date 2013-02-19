var services = require('./lib/execute-services.js');
//var authentication = require('./lib/authentication.js');

//services.startServices();

services.startListeningSocketIO();

//setTimeout(services.stopServices, 50000);
