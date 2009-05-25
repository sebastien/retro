<?python
# vim: ts=2 sw=2 et
?>
<html xmlns:py="http://purl.org/kid/ns#">

  <head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/retro.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
  </head>

  <body>

    <div id="title">
      <h1>Retro</h1>
      <h2>Wiki example</h2>
    </div>
    
    <p>Here is the list of available pages</p>
    <ul>
      <li py:for="page in pages"><a href='/pages/${page}'>${page}</a></li>
    </ul>
  </body>
</html>
