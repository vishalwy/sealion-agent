var socket_client = require('socket.io-client');
var socket = socket_client.connect('http://localhost:8000');

socket.on('connecting', function(something) {
    console.log(something);
});

socket.on('connect', function() {
    console.log("connected");
});

socket.on('update', function(msg) {
    console.log('Got message ' + JSON.stringify(msg));
});

socket.on('error', function(error) {
    console.log("Error in connection" + error);
});
