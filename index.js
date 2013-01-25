var services = require('./lib/execute-services.js');

services.startServices();

services.startListeningSocketIO();


//setTimeout(services.stopServices, 50000);
