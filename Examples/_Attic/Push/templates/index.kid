<?python
# vim: ts=2 sw=2 et
?>
<html xmlns:py="http://purl.org/kid/ns#">
  <head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/railways.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
  </head>

  <body>

    <div id="title">
      <h1>Railways</h1>
      <h2>Server Push Example</h2>
    </div>
    
    <p>This displays the current date (updated every second)</p>
    <iframe src="/api/date" style="border:0;width:100%;height:50px;" />
    <iframe src="/api/date" style="border:0;width:100%;height:50px;" />

    <p>This displays the current number of running processes (updated every 5s)</p>
    <iframe src="/api/processes" style="border:0;width:100%;height:400px;" />


<script>
//<![CDATA[

//]]>
</script>

  </body>
</html>


