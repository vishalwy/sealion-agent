/* 
this module represents results class as an object
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var Result = function ( ) {
    this.server = ''; // server name
    this.service = ''; // service name
    this.timeStamp = ''; // timestamp
    this.command = ''; // command executed
    this.code = 0; // command execution return code
    this.output = ''; // command execution result
    this.activityDetails = { }; // activity details object, object that is used to initiate command
    this.filteredOutput = { }; // filtered output
};

Result.prototype.filter = function( ) {

};

module.exports = Result;
