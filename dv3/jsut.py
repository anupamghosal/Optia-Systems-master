from concurrent.futures import ProcessPoolExecutor
from functools import partial
import numpy as np
import os
import dv3.audio
from nnmnkwii.datasets import jsut
from nnmnkwii.io import hts
from dv3.hparams import hparams
from os.path import exists
import librosa


def build_from_path(in_dir, out_dir, num_workers=1, tqdm=lambda x: x):
    executor = ProcessPoolExecutor(max_workers=num_workers)
    futures = []

    transcriptions = jsut.TranscriptionDataSource(
        in_dir, subsets=jsut.available_subsets).collect_files()
    wav_paths = jsut.WavFileDataSource(
        in_dir, subsets=jsut.available_subsets).collect_files()

    for index, (text, wav_path) in enumerate(zip(transcriptions, wav_paths)):
        futures.append(executor.submit(
            partial(_process_utterance, out_dir, index + 1, wav_path, text)))
    return [future.result() for future in tqdm(futures)]


def _process_utterance(out_dir, index, wav_path, text):
    sr = hparams.sample_rate

    # Load the audio to a numpy array:
    wav = dv3.audio.load_wav(wav_path)

    lab_path = wav_path.replace("wav/", "lab/").replace(".wav", ".lab")

    # Trim silence from hts labels if available
    if exists(lab_path):
        labels = hts.load(lab_path)
        assert labels[0][-1] == "silB"
        assert labels[-1][-1] == "silE"
        b = int(labels[0][1] * 1e-7 * sr)
        e = int(labels[-1][0] * 1e-7 * sr)
        wav = wav[b:e]
    else:
        wav, _ = librosa.effects.trim(wav, top_db=30)

    # Compute the linear-scale spectrogram from the wav:
    spectrogram =dv3.audio.spectrogram(wav).astype(np.float32)
    n_frames = spectrogram.shape[1]

    # Compute a mel-scale spectrogram from the wav:
    mel_spectrogram = dv3.audio.melspectrogram(wav).astype(np.float32)

    # Write the spectrograms to disk:
    spectrogram_filename = 'jsut-spec-%05d.npy' % index
    mel_filename = 'jsut-mel-%05d.npy' % index
    np.save(os.path.join(out_dir, spectrogram_filename), spectrogram.T, allow_pickle=False)
    np.save(os.path.join(out_dir, mel_filename), mel_spectrogram.T, allow_pickle=False)

    # Return a tuple describing this training example:
    return (spectrogram_filename, mel_filename, n_frames, text)
