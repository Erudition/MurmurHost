const mumble = require('mumble'),
    fs = require('fs'),
    lame = require('lame'),
    options = {
        key: fs.readFileSync(__dirname + '/key.pem'),
        cert: fs.readFileSync(__dirname + '/cert.pem')
    }

console.log('Connecting')
mumble.connect(process.argv[2], options, (error, connection) => {
    if (error) { console.error(error) }
    console.log('Connected')
    connection.authenticate(process.argv[3] || 'record')
    connection.on('initialized', () => {
        chan = connection.channelByName(process.argv[4] || 'Root')
        chan.join()
    })
    const encoder = new lame.Encoder({
        channels: 1,
        sampleRate: 48000,
        bitDepth: 16,
        bitRate: 128,
        outSampleRate: 44100,
        mode: lame.STEREO
    })
    connection.outputStream().pipe(encoder).pipe(fs.createWriteStream(__dirname + '/records/mumble-' + Date.now() + '.mp3'))
})
