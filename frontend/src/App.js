import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Search, Loader2, Play, Pause, SkipBack, SkipForward, Volume2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE = 'http://localhost:8000';

function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const [currentSong, setCurrentSong] = useState(null);
  const [songData, setSongData] = useState(null); // Lyrics & sync data
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const audioRef = useRef(null);

  const searchSongs = async (e) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/api/search`, { query });
      setResults(res.data.songs);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const playSong = async (song) => {
    setCurrentSong(song);
    setSongData(null);
    setLoading(true);
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }

    try {
      // 1. Process and get exact timings
      const res = await axios.post(`${API_BASE}/api/process`, {
        video_id: song.videoId,
        title: song.title,
        artist: song.artists[0]
      });

      setSongData(res.data);

      // 2. Load audio (serve static file from backend downloads folder using custom route, or we can use Blob)
      // For simplicity, we can fetch it or just point the audio tag if we serve the folder.
      // Wait, we need to serve downloads folder in main.py
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const onTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const lyricsContainerRef = useRef(null);

  // Auto-scroll lyrics
  useEffect(() => {
    if (songData && lyricsContainerRef.current) {
      const activeElement = lyricsContainerRef.current.querySelector('.active-lyric');
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [currentTime, songData]);

  return (
    <div className="h-screen w-full flex flex-col bg-black text-white relative overflow-hidden font-sans">

      {/* Background Blur */}
      {currentSong && currentSong.thumbnail && (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-30 blur-3xl transition-all duration-1000 scale-110"
          style={{ backgroundImage: `url(${currentSong.thumbnail})` }}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col z-10 p-6 overflow-hidden">

        {/* Search Bar */}
        <div className="w-full max-w-2xl mx-auto mb-8">
          <form onSubmit={searchSongs} className="relative flex items-center">
            <Search className="absolute left-4 text-gray-400" size={20} />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search for any song..."
              className="w-full bg-white/10 border border-white/20 rounded-full py-4 pl-12 pr-4 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 backdrop-blur-md"
            />
          </form>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto w-full max-w-6xl mx-auto flex">

          {/* Results List */}
          {(!currentSong || !songData) && (
            <div className="w-full">
              {loading && !currentSong && (
                <div className="flex justify-center mt-20">
                  <Loader2 className="animate-spin text-green-500" size={48} />
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.map((song, idx) => (
                  <div
                    key={idx}
                    onClick={() => playSong(song)}
                    className="bg-white/5 hover:bg-white/10 p-4 rounded-xl cursor-pointer transition flex items-center gap-4 backdrop-blur-sm border border-white/5"
                  >
                    <img src={song.thumbnail} alt={song.title} className="w-16 h-16 rounded-md object-cover shadow-lg" />
                    <div className="flex-1 truncate">
                      <h3 className="font-bold text-lg truncate">{song.title}</h3>
                      <p className="text-gray-400 truncate">{song.artists.join(', ')}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Player View */}
          {currentSong && loading && (
            <div className="flex-1 flex flex-col items-center justify-center">
              <Loader2 className="animate-spin text-green-500 mb-4" size={48} />
              <p className="text-xl font-medium">Processing audio & extracting lyrics...</p>
              <p className="text-gray-400 mt-2">This may take a moment depending on the song length.</p>
            </div>
          )}

          {currentSong && songData && (
            <div className="flex-1 flex flex-col md:flex-row gap-8 items-center md:items-start justify-center">
              {/* Album Art */}
              <div className="w-64 md:w-96 flex flex-col items-center">
                <motion.img
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  src={currentSong.thumbnail}
                  alt="cover"
                  className="w-full aspect-square object-cover rounded-2xl shadow-2xl"
                />
                <h2 className="text-3xl font-bold mt-6 text-center">{currentSong.title}</h2>
                <p className="text-xl text-gray-400 mt-2">{currentSong.artists.join(', ')}</p>
              </div>

              {/* Lyrics View */}
              <div
                ref={lyricsContainerRef}
                className="flex-1 h-[60vh] md:h-full overflow-y-auto no-scrollbar relative w-full flex flex-col gap-6 py-[40vh] px-4"
              >
                {songData.alignment.segments.map((seg, idx) => {
                  const isPast = currentTime > seg.end;
                  const isActive = currentTime >= seg.start && currentTime <= seg.end;

                  if (seg.is_instrumental) {
                    return (
                      <motion.div
                        key={idx}
                        className={`text-4xl md:text-6xl font-black text-center transition-all duration-300 ${isActive ? 'active-lyric text-white opacity-100 scale-110' : (isPast ? 'text-white/40' : 'text-white/20')}`}
                      >
                        🎵
                      </motion.div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      className={`text-2xl md:text-5xl font-bold transition-all duration-300 ${isActive ? 'active-lyric text-white opacity-100 scale-105' : (isPast ? 'text-white/40' : 'text-white/20')} leading-tight`}
                    >
                      {seg.words.map((wordObj, widx) => {
                        const wordPast = currentTime > wordObj.end;
                        const wordActive = currentTime >= wordObj.start && currentTime <= wordObj.end;

                        return (
                          <span
                            key={widx}
                            className={`inline-block mr-2 transition-colors duration-150 ${wordPast ? 'text-white' : (wordActive ? 'text-green-400' : '')}`}
                          >
                            {/* Letter level precise effect within the active word */}
                            {wordObj.word.split('').map((char, cidx) => {
                              const charDuration = (wordObj.end - wordObj.start) / wordObj.word.length;
                              const charStart = wordObj.start + (cidx * charDuration);
                              const charActive = currentTime >= charStart;

                              return (
                                <span
                                  key={cidx}
                                  className={`transition-colors duration-75 ${charActive && wordActive ? 'text-green-400' : (wordPast ? 'text-white' : '')}`}
                                >
                                  {char}
                                </span>
                              )
                            })}
                          </span>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Player Bar */}
      {currentSong && (
        <div className="h-24 bg-black/80 backdrop-blur-xl border-t border-white/10 flex items-center justify-between px-6 z-20">
          <div className="flex items-center gap-4 w-1/3">
            <img src={currentSong.thumbnail} alt="cover" className="w-14 h-14 rounded-md object-cover" />
            <div>
              <p className="font-bold">{currentSong.title}</p>
              <p className="text-xs text-gray-400">{currentSong.artists.join(', ')}</p>
            </div>
          </div>

          <div className="flex flex-col items-center w-1/3">
            <div className="flex items-center gap-6">
              <button className="text-gray-400 hover:text-white transition"><SkipBack size={24} /></button>
              <button
                onClick={togglePlay}
                className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition"
              >
                {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-1" />}
              </button>
              <button className="text-gray-400 hover:text-white transition"><SkipForward size={24} /></button>
            </div>
          </div>

          <div className="w-1/3 flex justify-end">
            <Volume2 className="text-gray-400" />
          </div>

          <audio
            ref={audioRef}
            src={songData ? `${API_BASE}/downloads/${currentSong.videoId}.mp3` : ''}
            onTimeUpdate={onTimeUpdate}
            onEnded={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            autoPlay
          />
        </div>
      )}
    </div>
  );
}

export default App;
