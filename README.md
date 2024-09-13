
# Improved program for using discord as a storage medium originally from [XDA-Developers article](https://www.xda-developers.com/discord-google-drive-cloud-storage/), link to the original github repository (https://github.com/Incipiens/GoogleDriveReplacementBot), modified by ATipsycal to add support for uploading multimple files, and entire folders, added a search feature that basically works by pasting the file name before all the parts of the file, then that can se searched by inputing the original file into the search box on the website. If you're running this locally, then the files will be in the downloaded folder, in the same directoy as app.py, if you want to run it on a server, don't. Also combined the stitch.py code into app.py, where it waits for all parts to download, stitches them, then deletes the parts. 
DON'T STORE SENSITIVE FILES, THE DISCORD SERVER CAN GET DELETED AT ANY TIME + THIS PROGRAM DOESN'T ENCRYPT FILES, SO ANYONE COULD TECHNICALLY STUMBLE UPON ANY PART OF YOUR FILES.


## How to deploy

Install the dependencies of the project, obviously you will need to have python installed (precisely version 3.12 or newer), cd into the directory that the app.py is installed in.

```bash
  cd (yourdirectory)
```

```bash
  pip install -r requirements.txt
```

Replace the BOT_TOKEN and the CHANNEL_ID in app.py with your client token and your channel ID. Make sure to have discord server, and a bot with the proper permissions in order for the program to work.

Following that, run

```bash
  python app.py
```

I set the default address for the local webpage is 127.0.0.2:5000, but that can be changed by modifying the WEBPAGE_IP and PORT parameters in the app.py files.
In the future I plan to add the token, and channel id as an input on the website to make it easier for everyone to use, but I guess if you got this far you can change a few variables.
## Documentation
Coming soon probably on [github](https://github.com/ATipsycal)

