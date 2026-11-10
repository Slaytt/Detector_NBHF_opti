%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% export_filter : reference for step 2 of port B (filter of a chunk)
%    Verification tooling, written by Claude (Anthropic); not part of the port itself.
%    The filter is copied from A* (run_bahia/DetectorNBHF_todos_passe_bande.m):
%    butter(5,...) with the A* modif 3 rule (high-pass if fcut_high >= fm/2),
%    then filter(butterBHF1,butterBHF2,senal) on each chunk and each channel,
%    with a zero initial state (no state carried between chunks).
%    Variable names and CSV columns keep A's names on purpose.
%
%    inputs  : all .wav files in jeu_equivalence/wav/
%    outputs : outputs/coefs_<fm>.txt     same format as A* modif 4 (one line per
%                                         coefficient, 'b ...' then 'a ...', %.17g)
%              outputs/filtered.csv       for each chunk and each channel: fingerprints
%                                         of the filtered signal senalHF
%              outputs/filtered_<fm>_head.bin, outputs/filtered_<fm>_tail.bin
%                                         first and last n_dump samples of senalHF,
%                                         chunk 1, channel 1, first file at that fm
%                                         (float64 little-endian), for a sample-by-sample diff
%
%    The fingerprints are NOT exact anymore (floating point sums, and filter /
%    lfilter may not do the operations in the same order): compare with a tolerance.
%    std_senalHF (N-1 normalisation) and umbral = std*coef_umbral prepare step 3.
%    ix_max is Octave's index (starts at 1) of the first maximum, as in [x, ix] = max(...).
%
%    Run: octave --no-gui octave_check/export_filter.m   (from Detector_py/)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clear
pkg load signal

here = fileparts(mfilename('fullpath'));
wav_dir = fullfile(here, '..', '..', 'jeu_equivalence', 'wav');
out_dir = fullfile(here, 'outputs');

% same as A*
t_trozo=29.99;
coef_umbral=9;
fcut_low=100000;
fcut_high=180000;

% number of samples dumped at the start and at the end of one chunk
n_dump = 100000;

files = dir(fullfile(wav_dir, '*.wav'));

fid = fopen(fullfile(out_dir, 'filtered.csv'), 'w');
fprintf(fid, 'fichier;i;canal;n;somme;somme_abs;somme_carres;std_senalHF;umbral;minimum;maximum;ix_max;x1;x2;x3;xn_2;xn_1;xn\n');

fm_done = [];
tic();

for k=1:numel(files)
  name = files(k).name;
  ArchivoSonido = fullfile(wav_dir, name);

  informations = audioinfo(ArchivoSonido);
  fm = informations.SampleRate;
  tamano_total = informations.TotalSamples;
  nbCanales = informations.NumChannels;

  % A* modif 3
  if fcut_high >= fm/2
    [butterBHF1,butterBHF2]=butter(5,fcut_low/(fm/2),'high');
  else
    [butterBHF1,butterBHF2]=butter(5,[fcut_low/(fm/2), fcut_high/(fm/2)]);
  end

  first_at_fm = ~any(fm_done == fm);
  if first_at_fm
    % same format as A* modif 4
    fid_coefs = fopen(fullfile(out_dir, sprintf('coefs_%d.txt', fm)), 'w');
    fprintf(fid_coefs, 'b %.17g\n', butterBHF1);
    fprintf(fid_coefs, 'a %.17g\n', butterBHF2);
    fclose(fid_coefs);
    fm_done(end+1) = fm;
  end

  tiempo_total_archivo_secundos=tamano_total/fm;
  N=floor(tiempo_total_archivo_secundos/t_trozo)+1;

  for i=1:1:N
    t_entrada=(i-1)*t_trozo;
    t_salida=t_entrada+t_trozo;
    inicioN = t_entrada * fm;
    finN = t_salida * fm;

    extrait=audioread(ArchivoSonido,[floor(max(inicioN,1)) floor(min(finN,tamano_total))]);

    for c=1:nbCanales
      senalHF = filter(butterBHF1,butterBHF2,extrait(:,c));
      n = length(senalHF);
      s = std(senalHF);
      [x, ix] = max(senalHF);
      fprintf(fid, '%s;%d;%d;%d;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%d;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g\n', ...
              name, i, c, n, sum(senalHF), sum(abs(senalHF)), sum(senalHF.^2), s, s*coef_umbral, ...
              min(senalHF), x, ix, ...
              senalHF(1), senalHF(2), senalHF(3), senalHF(n-2), senalHF(n-1), senalHF(n));

      if first_at_fm && i == 1 && c == 1
        fb = fopen(fullfile(out_dir, sprintf('filtered_%d_head.bin', fm)), 'w', 'ieee-le');
        fwrite(fb, senalHF(1:n_dump), 'double');
        fclose(fb);
        fb = fopen(fullfile(out_dir, sprintf('filtered_%d_tail.bin', fm)), 'w', 'ieee-le');
        fwrite(fb, senalHF(n-n_dump+1:n), 'double');
        fclose(fb);
        fid_src = fopen(fullfile(out_dir, sprintf('filtered_%d_source.txt', fm)), 'w');
        fprintf(fid_src, '%s;chunk 1;canal 1;n=%d;n_dump=%d\n', name, n, n_dump);
        fclose(fid_src);
      end
    end
  end
  printf('%2d/%d  %s  (%d chunks, %.0f s)\n', k, numel(files), name, N, toc());
  fflush(stdout);
end

fclose(fid);
