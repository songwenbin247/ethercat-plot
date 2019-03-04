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
    case "/js/dataTool.min.js" :
       fs.readFile('./http_server/js/dataTool.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/simplex.js" :
       fs.readFile('./http_server/js/simplex.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/ecStat.min.js" :
       fs.readFile('./http_server/js/ecStat.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/bmap.min.js" :
       fs.readFile('./http_server/js/bmap.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/echarts-gl.min.js" :
       fs.readFile('./http_server/js/echarts-gl.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/china.js" :
       fs.readFile('./http_server/js/china.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/echarts.min.js" :
       fs.readFile('./http_server/js/echarts.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/jquery-3.3.1.min.js" :
       fs.readFile('./http_server/js/jquery-3.3.1.min.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/js/world.js" :
       fs.readFile('./http_server/js/world.js', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/javescript'});
          res.write(data);
          res.end();});
	  break;
    case "/test.html" :
       fs.readFile('./http_server/test.html', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/html'});
          res.write(data);
          res.end();});
	  break;
    case "/i" :
       fs.readFile('./http_server/index.html', function(err, data) {
          res.writeHead(200, {'Content-Type': 'text/html'});
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
