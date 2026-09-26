// defs.h must land before the minifmod headers below: it typedefs
// BYTE/WORD/DWORD/LONG/BOOL (needed by Sound.h's own declarations), and
// every other .c file that reaches this point has already included it, so
// pulling it in here first keeps this file's own first-time compile
// (soundSystem.c) consistent with everyone else instead of leaving DWORD
// etc. undefined at this point.
#include "../../defs.h"

#ifndef _NO_MINIFMOD

	// minifmod/Sound.h unconditionally does `#include <windows.h>` and
	// `#include <mmsystem.h>` for four declarations: FSOUND_SoundBlock's WAVEHDR
	// member, FSOUND_WaveOutHandle (HWAVEOUT), FSOUND_Software_hThread (HANDLE)
	// and FSOUND_Software_DoubleBufferThread's LPDWORD parameter. Real windows.h
	// redefines BYTE/WORD/DWORD/LONG with different underlying types than
	// ../../defs.h, which every .c file that reaches this point has already
	// included (a hard typedef-redefinition error). None of the four are
	// otherwise used here: FSOUND_WaveOutHandle/FSOUND_Software_hThread/
	// DoubleBufferThread aren't referenced at all, and FSOUND_MixBlock.data is
	// read once in soundSystem.c but the result is discarded (dead local, never
	// passed on). So keep real windows.h out and hand Sound.h a byte-identical
	// stand-in for WAVEHDR instead (32 bytes, matches mmsystem.h's WAVEHDR
	// field-for-field) plus opaque HANDLE/HWAVEOUT/LPDWORD/DWORD. Skipped when
	// a real <windows.h> is already active in this translation unit (dr.c, via
	// SDL_opengl.h) - there it supplies the genuine types instead.
	//
	// DWORD is also typedef'd here (identical to defs.h's own int32 DWORD, so
	// a harmless redundant typedef where defs.h already supplied it): some
	// .c files reach here with SDL's own __WIN32__ already defined (set by
	// plain SDL.h, unrelated to real windows.h) but without ever including
	// real windows.h, which makes defs.h's `#ifndef __WIN32__` guard assume
	// windows.h already provides DWORD when it doesn't.
	#ifndef _WINDOWS_
		#define _WINDOWS_
		#define _INC_MMSYSTEM
		typedef int DWORD;
		typedef void *HANDLE;
		typedef void *HWAVEOUT;
		typedef DWORD *LPDWORD;
		typedef struct {
			char          *lpData;
			unsigned long dwBufferLength;
			unsigned long dwBytesRecorded;
			unsigned long dwUser;
			unsigned long dwFlags;
			unsigned long dwLoops;
			void          *lpNext;
			unsigned long reserved;
		} WAVEHDR;
	#endif

	#include "minifmod/Sound.h"
	#include "minifmod/Music.h"
	#include "minifmod/minifmod.h"

	#include "minifmod/Mixer.h"
	#include "minifmod/mixer_clipcopy.h"
	#include "minifmod/mixer_fpu_ramp.h"
	#include "minifmod/music_formatxm.h"
#endif

#include "fmod.h"

#ifndef _NO_MINIFMOD
	char   FMUSIC_StopSong_43D8E0(FMUSIC_MODULE* mod);
	char   FMUSIC_FreeSong_43D940(FMUSIC_MODULE *mod);
	char   FMUSIC_PlaySong_43DA40(FMUSIC_MODULE* musicModuleModified_456C24);
	FMUSIC_MODULE *   FMUSIC_LoadSong_43DC50(int size,  char *data, SAMPLELOADCALLBACK sampleloadcallback);
	int   FSOUND_Software_Fill_43DCB0(signed int a1, int a2);
	int   FSOUND_MixerClipCopy_Float32_43DE30(void *dest, void *src, long len);
	int   FSOUND_Mixer_FPU_Ramp_43DEA0(void *mixptr, int len);
	char   FMUSIC_XM_InstrumentVibrato_43E550(FMUSIC_CHANNEL *cptr, FMUSIC_INSTRUMENT *iptr);
	char   FMUSIC_XM_ProcessEnvelope_43E670(FMUSIC_CHANNEL *cptr, int *pos, int *tick, unsigned char type, int numpoints, unsigned short *points, unsigned char loopend, unsigned char loopstart, unsigned char sustain, int *value, int *valfrac, signed char *envstopped, int *envdelta, unsigned char control);
	char   FMUSIC_XM_ProcessVolumeByte_43E7A0(FMUSIC_CHANNEL *cptr, unsigned char volume);
	int   FMUSIC_XM_UpdateFlags_43E8C0(FMUSIC_CHANNEL *cptr, FSOUND_SAMPLE *sptr, FMUSIC_MODULE *mod);
	int   FMUSIC_XM_Resetcptr_43EB10(FMUSIC_CHANNEL *cptr, FSOUND_SAMPLE	*sptr);
	char   sub_43EBB0(int channelId, unsigned __int8 a2);
	unsigned __int64   sub_43EBD0(int channelId, signed int a2);
	int   FMUSIC_UpdateXMNote_43EC40(FMUSIC_MODULE *mod, int channelId, unsigned __int8 soundId, int a4, char volume);
	int   FMUSIC_UpdateXMEffects_43EDC0(FMUSIC_MODULE *mod);
	int   FMUSIC_UpdateXM_43EF50(FMUSIC_MODULE *mod); // weak
	char   FMUSIC_LoadXM_43EF60(FMUSIC_MODULE *mod, FSOUND_FILE_HANDLE *fp);

	int (  *  FSOUND_File_SetCallbacks_43F6B0(int (  *a1)(_DWORD), int (  *a2)(_DWORD), int (  *a3)(_DWORD, _DWORD, _DWORD), int (  *a4)(_DWORD), int (  *a5)(_DWORD)))(_DWORD);
	FSOUND_FILE_HANDLE * FSOUND_File_Open_43F720(int size, char *data, signed char type, int length);
	void   FSOUND_File_Close_43F770(FSOUND_FILE_HANDLE *handle);
	int   FSOUND_File_Read_43F790(void *buffer, int size, FSOUND_FILE_HANDLE *handle);
	int   FSOUND_File_Seek_43F7B0(FSOUND_FILE_HANDLE *handle);
	int   FSOUND_File_Tell_43F7D0(FSOUND_FILE_HANDLE *handle);

	void *  FSOUND_File_OpenCallback_43AD80(int size,char *name);
	void   FSOUND_File_CloseCallback_43ADD0(unsigned int handle);
	int   FSOUND_File_ReadCallback_43ADF0(void *buffer, int size, unsigned int handle);
	int   FSOUND_File_SeekCallback_43AE30(unsigned int handle, int pos, signed char mode);
	int   FSOUND_File_TellCallback_43AE70(unsigned int handle);

	typedef struct struct_userhandle
	{
		int		size;
		int		pos;
		char*   data;
	
	} struct_userhandle;
#endif