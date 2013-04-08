/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

/*
Function to log data
*/

function logData(data) {
    var date = new Date();
    console.log('[ ' + date.toJSON() + ' ]: ' + data);
}

module.exports = logData;
