%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% export_detection : reference for step 4 of port B (detection loop on one channel)
%    Verification tooling, written by Claude (Anthropic); not part of the port itself.
%    The loop is copied from A* (run_bahia/DetectorNBHF_todos_passe_bande.m), for
%    each chunk and each channel: filter, umbral = std*coef_umbral, then
%        while max(senalHF) > umbral
%            [x, ix] = max(senalHF)
%            spectre = abs(fft(senal(window around ix)))      % RAW signal, not senalHF
%            energieClic = mean(spectre(f1clic/1000:f2clic/1000))
%            energie_bande_passante = mean(spectre(f1/1000:f2/1000))
%            accept if energieClic > seuil*energie_bande_passante
%            senalHF(ix - floor(t_minimo*fm) : ix + floor(t_minimo*fm)) = 0  (clipped)
%    Every candidate (accepted or rejected) is written, in loop order, with the
%    intermediate values, so that B can be checked candidate by candidate.
%    Variable names and CSV columns keep A's names on purpose.
%
%    inputs  : all .wav files in jeu_equivalence/wav/
%    outputs : outputs/detection.csv         one line per candidate:
%                fichier;i;canal;k;ix;x;umbral;win_start;win_end;n_win;
%                energieClic;energie_bande_passante;accepte;date
%                k starts at 1 for each chunk x channel. ix, win_start, win_end are
%                Octave indices (start at 1, end included). date = (i-1)*t_trozo + ix/fm.
%              outputs/detection_chunks.csv  one line per chunk x channel:
%                fichier;i;canal;umbral;n_candidats;n_acceptes
%                (chunks with no candidate have a line here and none in detection.csv)
%
%    Exact equality expected on ix, win_start, win_end, accepte (integers / booleans).
%    x, umbral, the energies and date are floating point: compare with a tolerance.
%    A candidate whose energies are very close to the seuil ratio could flip: the test
%    must report the margin |energieClic - seuil*energie_bande_passante|.
%
%    Run: octave --no-gui octave_check/export_detection.m   (from Detector_py/, ~10 min)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clear
pkg load signal

here = fileparts(mfilename('fullpath'));
wav_dir = fullfile(here, '..', '..', 'jeu_equivalence', 'wav');
out_dir = fullfile(here, 'outputs');

% same as A*
coef_umbral=9;
seuil=0.4;
fcut_low=100000;
fcut_high=180000;
f1clic=120000;
f2clic=140000;
f1=30000;
f2=90000;
t_minimo=1/1000;
t_trozo=29.99;

files = dir(fullfile(wav_dir, '*.wav'));

fid = fopen(fullfile(out_dir, 'detection.csv'), 'w');
fprintf(fid, 'fichier;i;canal;k;ix;x;umbral;win_start;win_end;n_win;energieClic;energie_bande_passante;accepte;date\n');
fid_chunks = fopen(fullfile(out_dir, 'detection_chunks.csv'), 'w');
fprintf(fid_chunks, 'fichier;i;canal;umbral;n_candidats;n_acceptes\n');

tic();

for kf=1:numel(files)
  name = files(kf).name;
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

  tiempo_total_archivo_secundos=tamano_total/fm;
  N=floor(tiempo_total_archivo_secundos/t_trozo)+1;
  n_total = 0;

  for i=1:1:N
    t_entrada=(i-1)*t_trozo;
    t_salida=t_entrada+t_trozo;
    inicioN = t_entrada * fm;
    finN = t_salida * fm;

    extrait=audioread(ArchivoSonido,[floor(max(inicioN,1)) floor(min(finN,tamano_total))]);

    for c=1:nbCanales
      % same lines as A for senal1 / senal1HF / umbral1 (and senal2 ...)
      senal = extrait(:,c);
      senalHF=filter(butterBHF1,butterBHF2,senal);
      umbral = std(senalHF)*coef_umbral;

      k = 0;
      n_acceptes = 0;
      while (max(senalHF)>umbral)
        k = k + 1;
        [x, ix] = max(senalHF);

        win_start = max(ix-floor(fm/2000 -1),1);
        win_end = min(ix+floor(fm/2000),length(senal));
        spectre=abs(fft(senal(win_start:win_end)));
        energieClic = mean(spectre(f1clic/1000:f2clic/1000));
        energie_bande_passante=mean(spectre(f1/1000:f2/1000));
        accepte = (energieClic>seuil*energie_bande_passante);
        n_acceptes = n_acceptes + accepte;
        fecha = (i-1)*t_trozo+ix/fm;

        fprintf(fid, '%s;%d;%d;%d;%d;%.17g;%.17g;%d;%d;%d;%.17g;%.17g;%d;%.17g\n', ...
                name, i, c, k, ix, x, umbral, win_start, win_end, win_end-win_start+1, ...
                energieClic, energie_bande_passante, accepte, fecha);

        senalHF(max(1,ix-floor(t_minimo*fm)):min(length(senal),ix+floor(t_minimo*fm)))=0;
      endwhile

      fprintf(fid_chunks, '%s;%d;%d;%.17g;%d;%d\n', name, i, c, umbral, k, n_acceptes);
      n_total = n_total + k;
    end
  end
  printf('%2d/%d  %s  (%d chunks, %d candidates, %.0f s)\n', kf, numel(files), name, N, n_total, toc());
  fflush(stdout);
end

fclose(fid);
fclose(fid_chunks);
