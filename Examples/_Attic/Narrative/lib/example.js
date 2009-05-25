// The display function uses the Narrative JavaScript `->` operator to wait for
// the future to have its value. This means that the call to display will create
// a "lightweight thread" that will block until the Future has its value
// assigned.
function display(text, future) {
	alert("" + text + "\n" + future.get->())
}

function test() {
	alert("Narrative JavaScript test")
	Retro.POST('values','name=pouet&value=pouetvalue')
	var channel = new Retro.AsyncChannel()
	// Here we have the interesting thing about using NJS : we ask the display
	// of the channel value, but the first call to `delayedvalues` will take one
	// second (the server will take one second to generate the response).
	//
	// So in practive, the first alert to be displayed will be the `value:...`,
	// while the second alert will be the `delayed values`.
	//
	// This example may not be *that* useful in itself, but it illustrates how
	// easy it is to deal with asynchronous channels in a synchronous style.
	display("Delayed values: ", channel.get('delayedvalues'))
	display("values:         ", channel.get('values'))
}
