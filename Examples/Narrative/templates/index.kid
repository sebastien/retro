<?python
# vim: ts=2 sw=2 et
?>
<html xmlns:py="http://purl.org/kid/ns#">

  <head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/narrative.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/railways.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/prevail.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
  </head>

  <body >

    <div id="title">
      <h1>Railways</h1>
      <h2>Narrative JavaScript example</h2>
    </div>

    <p>You should see a series of pop-ups appearing very soon.</p>
    <script>
    // <![CDATA[

    // This demonstrates the use of burst channels used with Futures.
    // This is particularily useful because the requests will be aggregated, and then will be fired
    // at once when the timeout (500ms) expires. At that moment, the futures will be triggered.
    
    eval(Railways.compileNJS({url:'lib/example.js'}))
    test()

    /*
    var burst_channel = new Railways.BurstChannel("/")
    burst_channel.get("/api/pr:collections").onSet(function(v){
      alert("Available collections:" + v)
    })
    burst_channel.post("/rw:interface","value='Here is some value'").onSet(function(v){
      alert("Available interfaces:" + v)
    })
    burst_channel.post("/values","name=pouet&value=pouetvalue")
    burst_channel.get("/values").onSet(function(v){
      alert("Values set:" + v)
    })
    */
    // ]]>
    </script>

  </body>
</html>


