var http = require('http');
var fs = require('fs');

http.createServer(function (req, res) {
  switch(req.url){	
    case "/js/style.css" :
       fs.readFile('./http_server/js/style.css', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/ccs'});
          res.write(data);
          res.end();});
          break;
    case "/js/main.js" :
       fs.readFile('./http_server/js/main.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
          break;
    case "/js/jquery-1.10.2.js" :
       fs.readFile('./http_server/js/jquery-1.10.2.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    default:
       fs.readFile('./http_server/echo.html', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/html'});
          res.write(data);
          res.end();});
  }
}).listen(8080);
