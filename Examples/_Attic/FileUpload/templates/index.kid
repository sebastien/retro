<?python
# vim: ts=2 sw=2 et
?>
<html xmlns:py="http://purl.org/kid/ns#">

  <head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/retro.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
    <style>
    .progress {
      display: block;
      width: 100px;
      height: 24px;
      padding: 1px;
      border: 1px solid #AAAAAA;
    }
    #progress {
      display: block;
      width: 0px;
      height: 24px;
      background: url("/lib/progress.png");
    }
    .hidden {
      display: none;
    }
    .upload {
      padding: 10px;
      border: 1px solid rgb(22, 130, 178);
    }
    </style>
  </head>

  <body>

    <div id="title">
      <h1>Retro</h1>
      <h2>AJAX file-upload example</h2>
    </div>
    
    <p>Click on the following button to upload a file</p>
    <div id="formcontainer">
      <table border="0" class="upload" align="center">
      <tr id="upload">
        <td colspan="2">
          <form  id="upload-form" action="/api/upload" method="post" enctype="multipart/form-data" onsubmit="return uploadForm(this)">
            <input id="document_file" name="document[file]" size="30" type="file" />
            <input name="commit" type="submit" value="Upload" />
            <iframe id="upload-target" name="upload-target" src="" style="width:0px;height:0px;border:0"></iframe>
          </form>
        </td>
      </tr>
      <tr id="upload-info" class="hidden">
        <td ><div class="progress"><div id="progress" ></div></div></td>
        <td ><div id="percent"></div></td>
      </tr>
      </table>
    </div>

<script language="javascript" type="text/javascript">
// <![CDATA[

// NOTE: Another trick, that works when you do not want to use an iframe is to a different server
// to post to. For instance, if the page is accessed as http://localhost/index.html, the you could
// post to http://127.0.0.1/api/upload without the post blocking from doing other GET requests.
// This is a better alternative if you have the possibility to have multiple names for your
// server.

function uploadForm(form) {
  form.target = 'upload-target'
  $('upload-info').style.display = "block"
  $('upload').style.display      = "none"
  updatePercentage()
  return true
}

function updatePercentage() {
    function u(value) {
      if ( $('percent').childNodes.length > 0 ) 
      { $('percent').removeChild($('percent').childNodes[0]) }
      $('percent').appendChild(document.createTextNode(value + "%"))
    }

    function f(req) {
      var value = req.responseText
      console.log("Progress " + value)
      Element.setStyle($('progress'), {width:value + "px"})
      u(value)
      if ( value < 100 ) {
        window.setTimeout(updatePercentage, 1000)
      } else { window.setTimeout(function(){
        $('upload-info').style.display = "none" ; $('upload').style.display = "block"
        u(0)
        $('upload-target').src = 'blank'
      }, 2000) }
    }
    // NOTE: IE does not update the value properly when requesting a with a POST...
    new Ajax.Request("/api/upload/progress", {method:"post", asynchronous:true, onSuccess:f})
}

// ]]>
</script>
  </body>
</html>


