%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Teste un détecteur de NBHF sur un fichier annoté
% entrées : 	le fichier .wav de référence
%		un fichier de détections 'vraies' de référence (dates en s)
% sorties : 	un fichier de sortie avec pour chaque test le seuil, l'umbral, la durée de calcul, les taux FN et VP
%		une courbe ROC pour quelques seuils et umbrals distincts
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


clear
close all
pkg load signal


graphics_toolkit('gnuplot') 


% frecuencia del filtro paso alto (Hz)
fcut_low=100000
fcut_high=180000

% frecuencia del clic : bande [f1clic;f2clic]
f1clic=120000
f2clic=140000


% frecuencia de comparacion : bande [f1;f2]
f1=30000
f2=90000

% tiempo minimo entre dos clicks (en s) : es decir no vamos a registrar dos clicks diferentes si el tiempo entre los dos esta menos que t_minimo.
% para delfines costeros : 100 micro_s = 0.1 ms = 1/10000 s   
% Algunos buzz tienen un ICI menos de 2 ms , pero algunos clicks tienen rebotes a mas de 3 ms ... 
t_minimo=1/1000
% umbral para que clics detactados en ambos canales sean igualados (0,4 ms TDOA max)
t_fusion = 5/10000;
% t_trozo : tiempo de cada trozo analizado (en s)
t_trozo=40;
%t_detect : seuil en temps pour la comparer la détection d'un click à la référence
t_detect = 0.0015;

% Lieu ?
printf('\n')
%printf('Lieu ?  \n ')
Lieu = input('Lieu ?  ','s') ;
Annee = input('Annee ?  ','s');
printf('\n')


% Archivos necesarios para el programa :
ArchivoSonido = ['FichierTest_' Lieu '.wav'];
ArchivoRef = ['reference_' Lieu '.txt']

% Archivo de resultados
ArchivoRes = ['Res_' Lieu Annee '_BP' int2str(f1/1000) int2str(f2/1000) '_Clic' int2str(f1clic/1000) int2str(f2clic/1000) '.txt']


%%% Lectura de los parametros del archivo de sonido
[tamano_total, nbCanales] = wavread(ArchivoSonido, "size");
[s,fm,dyn] = wavread(ArchivoSonido,[1 10]);
clear s;

% Filtros
%[butterHF1,butterHF2]=butter(5,fcut/(fm/2),'high');
[butterBHF1,butterBHF2]=butter(5,[fcut_low/(fm/2), fcut_high/(fm/2)]);

% tiempo total del archivo (en segundos)
tiempo_total_archivo_secundos=tamano_total/fm;
%t_trozo = tiempo_total_archivo_secundos;

% numero de trozos de t_trozo s
N=floor(tiempo_total_archivo_secundos/t_trozo)+1;

%  durée de fichier analysée (imin>0, imax<N+1)
imin=1;
imax=N;

% seleción de las referencias que corresponden a la porción del archivo que se analizará
Ref1 = textread(ArchivoRef,'%f');
Ref2 = Ref1(Ref1>((imin-1)*t_trozo));
Reference = Ref2(Ref2<(imax*t_trozo));


% umbrales :
ValeursUmbral=[6 7 8 9 10]

% Seuils :
ValeursSeuil=[0.6 0.65 0.7 0.75 0.8 0.85 0.9]


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% BOUCLE SUR LES MORCEAUX DE FICHIERS (i)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

tic()

Detection_HF1=[];
Intensite_HF1=[];
SNR_HF1=[];
Detection_HF2=[];
Intensite_HF2=[];
SNR_HF2=[];

for i=imin:1:imax

   t_entrada=(i-1)*t_trozo;
   t_salida=t_entrada+t_trozo;

   %%% extracto
   inicioN = t_entrada * fm;
   finN = t_salida * fm;
   extrait=wavread(ArchivoSonido,[floor(max(inicioN,1)) floor(min(finN,tamano_total))]);

   %%% filtro
   senal1 = extrait(:,1);
   senal1HF=filter(butterBHF1,butterBHF2,senal1);

   %%% busqueda de las partes de la senal superiores al umbral mas pequeño


   % canal 1
   ruido1 = std(senal1HF);
   umbral1 = ruido1*min(ValeursUmbral);

   Det_HF=[];
   Int_HF=[];
   SN_HF=[];
 
   while (max(senal1HF)>umbral1)                                                     
      [x, ix] = max(senal1HF);
      spectre=abs(fft(senal1(max(ix-floor(fm/2000 -1),1):min(ix+floor(fm/2000),length(senal1)))));
      energieClic = mean(spectre(f1clic/1000:f2clic/1000));
      energieMF=mean(spectre(f1/1000:f2/1000));
      Det_HF = [Det_HF;(i-1)*t_trozo+ix/fm ];
      Int_HF = [Int_HF; x/ruido1]; 
      SN_HF = [SN_HF;energieClic/energieMF];
      % Mise à zéro de la zone autour du max
      senal1HF(max(1,ix-floor(t_minimo*fm)):min(length(senal1),ix+floor(t_minimo*fm)))=0;
   endwhile	

   %% compilation sur tous les trozos
   Detection_HF1 = [Detection_HF1 ; Det_HF];   
   Intensite_HF1 = [Intensite_HF1 ; Int_HF];
   SNR_HF1 = [SNR_HF1 ; SN_HF];
	
   % canal 2
   if (nbCanales > 1)                                                           
      %%% filtro 
      senal2 = extrait(:,2);
      senal2HF=filter(butterBHF1,butterBHF2,senal2);
      ruido2 = std(senal2HF);
      umbral2 = ruido2*min(ValeursUmbral);

      Det_HF2=[];
      Int_HF2=[];
      SN_HF2=[];
 	
      while (max(senal2HF)>umbral2)                                                     
	[x, ix] = max(senal2HF);
        spectre=abs(fft(senal2(max(ix-floor(fm/2000 -1),1):min(ix+floor(fm/2000),length(senal2)))));
        energieClic = mean(spectre(f1clic/1000:f2clic/1000));
        energieMF=mean(spectre(f1/1000:f2/1000));
        Det_HF2 = [Det_HF2;(i-1)*t_trozo+ix/fm ];
        Int_HF2 = [Int_HF2; x/ruido2]; 
        SN_HF2 = [SN_HF2;energieClic/energieMF];
	% Mise à zéro de la zone autour du max
       	senal2HF(max(1,ix-floor(t_minimo*fm)):min(length(senal2),ix+floor(t_minimo*fm)))=0;
      endwhile	

      Detection_HF2 = [Detection_HF2 ; Det_HF2];   
      Intensite_HF2 = [Intensite_HF2 ; Int_HF2];
      SNR_HF2 = [SNR_HF2 ; SN_HF2];

   endif

endfor

% Trois (grands) vecteurs, avec toutes les détections HF possibles, leurs intensités, et leur Signal sur Bruit

DureePretraitement = toc

% Archivos de resultados :
% Todas detecciones
fileID = fopen(ArchivoRes,'w');
fprintf(fileID,'Detecteur de clics sup à %d kHz et inf a %d kHz.  \n',fcut_low,fcut_high);
fprintf(fileID,'BP du clic %d - %d . BP de comparaison %d - %d . Canaux: %d . \n',f1clic, f2clic, f1, f2, nbCanales);
fprintf(fileID,'Analysés : imin = %d à imax = %d soit %f s à %f s. Nb de signaux vrais : %d . Durée prétraitement : %f\n',imin,imax,(imin-1)*t_trozo,imax*t_trozo,length(Reference),DureePretraitement );
fprintf(fileID,'Seuil \t Umbral \t Duree \t Detections 1 \t Pics HF 1 \t Detections 2\t Pics HF 2 \t Detections Totales \t Tx VP \t Tx FN \n');


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%% Loop de los umbrales (j)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

for j=1:1:length(ValeursUmbral)
	Umbral = ValeursUmbral(j);
	Detection_HF1_U = Detection_HF1(Intensite_HF1>Umbral);
	SNR_HF1_U = SNR_HF1(Intensite_HF1>Umbral);
        if (nbCanales>1)
		Detection_HF2_U = Detection_HF2(Intensite_HF2>Umbral);
		SNR_HF2_U = SNR_HF2(Intensite_HF2>Umbral);
	else
		Detection_HF2_U = Detection_HF1_U;
	endif 

	%%%%%%%%%%%%%% loop sur les seuils
	for k=1:1:length(ValeursSeuil)
		tic()
		% Choix des clics
		Seuil = ValeursSeuil(k);
		Clics1 = Detection_HF1_U(SNR_HF1_U>Seuil);

		% Si il y a deux canaux
		if (nbCanales>1)
			Clics2 = Detection_HF2_U(SNR_HF2_U>Seuil);

	       		% fusion des clicks détectés sur les deux canaux
	       	        Colonne1=[Clics1;Clics2];
			Colonne2=[ones(length(Clics1),1);2*ones(length (Clics2),1)];
               		dates_clicks = [Colonne1 Colonne2];
               		dates_clicks = sortrows(dates_clicks);
               		n=1;
	       		while (n<(length(dates_clicks)-1))
                   		if (abs(dates_clicks(n+1,1)-dates_clicks(n,1))<t_fusion)
                       		   dates_clicks = [dates_clicks(1:n,:);dates_clicks(n+2:length(dates_clicks),:)] ;
                   		endif 
               			n=n+1;
	       		endwhile
	        else
               		dates_clicks = [Clics1 ones(length(Clics1),1)];  
               		dates_clicks = sortrows(dates_clicks);
               		Clics2 = Clics1; 
           	endif

		Detections=dates_clicks(:,1);

		% On choisit d'inclure les rebonds -dans les references et dans les détections, j'enlève ce paragraphe
		%{
		%%%% Tri des rebonds en fonction d'une moyenne des ICI avant et après 
	        ICI = circshift(Detections,-1) - Detections;
	        ICI = ICI(1:length(ICI)-1);

		for l=6:1:(length(ICI)-5)
		   ICI_avant = mean(ICI(max(1,l-5):max(1,l-1)));
	           ICI_apres = mean(ICI(min(l+1,length(ICI)):min((l+5),length(ICI))));	 
	           if ICI(l)<0.004
	               if ((2*ICI(l))<ICI_avant)&((2*ICI(l))<ICI_apres)
	                    Detections = [Detections(1:l);Detections(l+2:length(Detections))];
	                    ICI = [ICI(1:l);ICI(l+2:length(ICI))];                  
        	       endif
        	   endif
        	   if l>(length(ICI)-2) 
        	     break
        	   endif 
		endfor
		%}

		nbclicks= length(Detections);

		nbHF1 = length(Detection_HF1_U);
		nbHF2 = length(Detection_HF2_U)*(nbCanales>1);

		nbclicks1= length(Clics1);
	        nbclicks2= length(Clics2)*(nbCanales>1);  

		%%%%%%%%%%%%%%%%%%%%%%%%
        	% Calcul des paramètres de la détection
        	%%%%%%%%%%%%%%%%%%%%%%%%
		VP = Detections - Detections;
		FN = Reference - Reference;

		%%%%%%%%%%%%%%%%%%%%%%%%%%
		% Boucle sur les détections pour calculer le taux de vrais positifs (sur les signaux détectés, la proportion de vrais signaux = 		% précision)
		%%%%%%%%%%%%%%%%%%%%%%%%%%
		for i=1:1:length(Detections)
	   		for l=1:1:length(Reference)
	      		     VP(i)= VP(i) + ( abs(Detections(i) - Reference(l) )< t_detect );
	   		endfor
           	        VP(i) = min(VP(i),1);	
		endfor
		TauxVP(k,j) = sum(VP)/length(Detections);

		%%%%%%%%%%%%%%%%%%%%%%%%%%
		% Boucle sur les références pour calculer les faux négatifs (sur tous les signaux vrais, la proportion de signaux non détectés = 1 - Recall, opposé du Rappel, ou de la sensibilité)
		%%%%%%%%%%%%%%%%%%%%%%%%%%
		
	        for l=1:1:length(Reference)
		   for i=1:1:length(Detections)
	              FN(l)= FN(l) + ( abs(Detections(i) - Reference(l) ) < t_detect );
		   endfor	
	           FN(l) = min(FN(l),1);
		endfor
	        
		FN = ones(length(Reference),1) - FN;
		TauxFN(k,j) = sum(FN)/length(Reference);

		Duree = toc;      
		% ecriture du fichier de sortie
		fprintf(fileID,'%f \t %d \t %f \t %d \t %d \t %d \t %d \t %d \t %f \t %f \n',Seuil, Umbral, Duree, nbclicks1, nbHF1, nbclicks2, nbHF2, nbclicks, TauxVP(k,j), TauxFN(k,j));

	endfor % fin de la boucle sur les seuils (j)

endfor % fin de la boucle sur les umbrals (k)


fclose(fileID);

%%%%%%%%%%%%%%%%%%%%%%%
% Construction de la courbe ROC
%%%%%%%%%%%%%%%%%%%%%%%
Titre = ['Caracteristique Detecteur ' Lieu Annee ' - Umbrales : ' int2str(ValeursUmbral)];
%Titre = ['ROC Curve - Highblue'];
ArchivoImagen = ['ROC_' Lieu '_BP' int2str(f1/1000) int2str(f2/1000) '_Clic' int2str(f1clic/1000) int2str(f2clic/1000) '.eps'];
legende={};
colororder = get (gca, "colororder");

figure(1)
for k=1:1:length(ValeursSeuil)
  h = plot(1-TauxFN(k,:),TauxVP(k,:),'-*');
%  set (h, "color", colororder(k,:));
  legende = {legende{:},['Thr  ',num2str(ValeursSeuil(k))]};
  hold on;
endfor
hold off;
axis([0 1 0 1]);
ylabel('Precision','fontweight','bold','fontsize',18)
xlabel('Sensibilite','fontweight','bold','fontsize',18)
%ylabel('True positive rate','fontweight','bold','fontsize',18)
%xlabel('False negative rate','fontweight','bold','fontsize',18)
title(Titre,'fontweight','bold','fontsize',18)
legend (legende, 'location', 'east');




print(ArchivoImagen,'-depsc')


Titre = ['Caracteristics ' Lieu Annee ' - Umbrales : ' int2str(ValeursUmbral)];
ArchivoImagen = ['ROC_' Lieu '_BP' int2str(f1/1000) int2str(f2/1000) '_Clic' int2str(f1clic/1000) int2str(f2clic/1000) 'English.eps'];

legende={};
colororder = get (gca, "colororder");

figure(2)
for k=1:1:length(ValeursSeuil)
  h = plot(1-TauxFN(k,:),TauxVP(k,:),'-*');
%  set (h, "color", colororder(k,:));
  legende = {legende{:},['Thr  ',num2str(ValeursSeuil(k))]};
  hold on;
endfor
hold off;
axis([0 1 0 1]);
%ylabel('Taux de vrais positifs','fontweight','bold','fontsize',18)
%xlabel('Taux de faux negatifs','fontweight','bold','fontsize',18)
ylabel('Precision','fontweight','bold','fontsize',18)
xlabel('Recall','fontweight','bold','fontsize',18)
title(Titre,'fontweight','bold','fontsize',18)
legend (legende, 'location', 'east');




print(ArchivoImagen,'-depsc')



		

