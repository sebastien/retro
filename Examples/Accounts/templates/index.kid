<?python
# vim: ts=2 sw=2 et
?>
<html xmlns:py="http://purl.org/kid/ns#">

  <head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/scriptaculous/scriptaculous.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/railways.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/prevail.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
    <style type="text/css">
    .login{
      display: block;
      float: left;
      width: 120px;
    }
    </style>
  </head>

  <body onload="init()">

    <div id="title">
      <h1>Railways</h1>
      <h2>Accounts example</h2>
    </div>
    
    <h3>Existing accounts</h3>
    <div>
      <div id="users" />
      <hr />
      <form id='user-add' action='/api/user/new'>
        <input type="text"     name="login"    value="User login" />
        <input type="password" name='password' />
        <input type="button"   value="Add user" onclick="Railways.SUBMIT('user-add')"/>
      </form>
    </div>

    <div id='floats' />

    <script language="javascript">
    var users = undefined
    function init() {
      console.log("Initializing")
      world = new Prevail.World("/api")
      users = world.collection("users")
      // Creates the HTML elements epresenting the users
      users.each( function(user) {
        var DIV_user = html.DIV(
          html.SPAN({_:'user'},
            html.SPAN({_:'login',    id:user._cached_id+".login"},    user.login()), 
            html.A({href:'#', onclick:'users.deleteByKey("' + user._key +'")'}, "delete user")
        ))
        user._addView(DIV_user)
        $("users").appendChild(DIV_user)
      })
      // Sets up the user addition form validation
      var user_add_form = new Railways.UI.Form($('user-add'), {
        login     : {
          validate:users.validator('login'),
          message:'Login already used, please choose another one',
          required:true
        },
        password  : { validate:users.validator("password"), required:true},
        submit    : { requires:['login','password'] },
      })
    }
    </script>
  </body>
</html>


