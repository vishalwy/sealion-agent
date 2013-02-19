
var Sealion = { };

Sealion.Result = function ( ) {
    this.server = '';
    this.service = '';
    this.timeStamp = '';
    this.command = '';
    this.code = 0;
    this.output = '';
    this.activityDetails = { };
    this.filteredOutput = { };
};

Sealion.Result.prototype.filter = function( ) {

};

module.exports = Sealion.Result;
