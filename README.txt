========== DEPENDENCIES ==========

Install dependencies by executing creating an new conda environment from environment.yml file:

$ conda env create -n ENVNAME --file environment.yml

Or create a new environment first then install dependencies using the requirements.txt file:

$ pip install -r requirements.txt

To train, use, or evaluate the weighted model (train_weighted_model.py) an environment should be created using environment2.yml or install dependencies from requirements2.txt

============ EXECUTION ===========

To test and evaluate the model on the test set provided, run "python evaluation.py" in an environment with all the dependencies installed.

To run entire project from scratch, the order of execution is:

==== NOT PRESENT ====
1. nist_scraper.py
2. sdbs_scraper.py

3. preprocessing.py
    -> Convert GIF images to PNG (for sdbs)
    -> SDBS:
        - Each file gets saved in the following format: {sdbs_id}_{medium_of_spectra}.gif 
            * medium_of_spectra can be liquid, nujol or KBr
            * have one .gif file for each of these
        - Confert .gif to .PNG 
        - Store metadata of compound inside other/{sdbs_id_}_{others}
            * This contains InChi identifier (most important) and basically everything else
        - Format pictures into same-sized frames
    -> NIST:
        - Each file gets saved in the format of {nist_id}_.jdx
            * .jdx file format contains spectroscopy data in binaries
            * last '_' is really important!
        - Another .inchi file that keeps track of each InChi identifier for each compound
            * Stored inside {nist_inchi_path}/{nist_id}.inchi
    -> They then all get transformed to .csv datasets

4. split_data.py
    -> Loads .csv input and label datasets
        - Renames columns to use integer indices
    -> Encodes unique InChI identifiers as numerical IDs
        - extracts InChI IDs from y_df[fgs] (functional group string column)
        - maps them to integers and stores them in y[fgs+2] and x_df[602]
            * honestly no clue why, there must be a better way to do this
    -> Converts dataframes to NumPy arrays 
        - output X and y
    -> Splits data into test and training + validation sets (test set is 20% of the data)
        - MultilabelStratifiedShuffleSplit (msss) used to +- evenly distribute functional groups across the split
        - results in X_train_val, y_train_val, X_test, y_test
    -> Splits train/validate 4-fold
        - MultilabelStratifiedKFold used to generate four train/val splits
        - stored as: X_train_1, y_train_1, X_val_1, y_val_1 (up to fold 4)
    -> Sets find themselves in a .pickle (file)

5. data_augmentation.py
    -> Reads the .pickle
        - Extracts X_train_1, y_train_1, X_val_1, y_val_1, X_test, y_test
            * only fold 1 + test sets
    -> Combines training and validation sets (X_train_val, y_train_val)
        - these sets do not contain metadata columns; full versions kept as X/y_train_val_ids 
    -> Creates subsets of training data for oversampling control  
        - uses msss, extracts 25%, 50%, 75% & 100% of data from X/y_train_val
            * Example key: y_train_val_25, X_train_val_100 etc.
    -> Augmentation functions:
        - horizontal_aug - pseudorandomly shifts the spectra left/right (+-1 to +-10 wavenumbers)
            * Example key: X_train_val_h_50 (for the 50% training data set)
        - vertical_aug - adds slight noise to the spectrum (+- 5% of y value) 
            * Example key: y_train_val_v_75 
        - linear_comb - combine 2 spectra of compounds with the same InChI ID using random weights (summing to 1)
            * Input is X/y_train_val_ids
		    * Example key: X_train_val_lc_100
    -> Creates a data dictionary containing all augmented sets 
		- Keys: X_train_val_25, X_train_val_h_50, X_train_val_v_75, X_train_val_lc_100, X_test
		- same for y

6. hyperparameter_optimization.py
    -> Performs Bayesian optimization of CNN hyper-parameters using Gaussian Process minimization (skopt)
    -> Defines the search space for eight parameters:
        - num_dense_layers: number of dense layers (1–4)
        - num_filters: number of filters in the first Conv1D layer (4–32)- dense_divisor: factor to reduce dense nodes after each layer (0.25–0.8)
        - num_cnn_layers: total Conv1D layers (1–5)- dropout: dropout rate between dense layers (0–0.5)- batch_size: training batch size (8–512)
        - kernel_size: size of the convolutional kernel (2–12)- num_dense_nodes: nodes in the first dense layer (1000–5000)
    -> Loads processed data from processed_dataset.pickle, then:
        - Drops metadata columns from X_train_1, X_val_1, X_test, y_train_1, y_val_1, y_test
        - Reshapes inputs to (n_samples, 600, 1)
    -> Implements create_model(...) to build a Keras Functional CNN given hyper-parameters:
        - Stacks specified number of Conv1D + BatchNorm + ReLU + MaxPooling1D layers, doubling filters each time
        - Flattens output, then adds ordered dense layers with dropout and divisor-based node reduction
        - Final sigmoid output for multilabel classification-> Defines a custom Metrics callback to compute micro F1, precision, and recall on validation set after each epoch
    -> Uses fitness(...) as the objective for gp_minimize:
        - Trains each candidate model with EarlyStopping, ReduceLROnPlateau, ModelCheckpoint, and Metrics
        - Records validation loss, stopping epochs, and model names via CheckpointSaver
    -> Runs 50 optimization calls in parallel (n_jobs=-1), then aggregates results into searched_parameters.pkl and searched_parameters.csv

7. train_model.py
    -> Trains the final CNN model using the best hyper-parameters found
    -> Defines train_model(X_train_val, y_train_val, num_fgs, aug, num, weighted):
        - Reshapes X_train_val to (n_samples, 600, 1)
        - Builds a fixed architecture:* Conv1D (31 filters, kernel=11) + BatchNorm + ReLU + MaxPooling1D* Conv1D (62 filters, kernel=11) + BatchNorm + ReLU + MaxPooling1D* Flatten* Dense(4927) + ReLU + Dropout(0.486)* Dense(2785) + ReLU + Dropout(0.486)* Dense(1574) + ReLU + Dropout(0.486)* Output Dense(num_fgs) + Sigmoid
        - If weighted == 1, computes class weights from y_train_val to balance positive/negative classes, and applies a custom weighted binary cross-entropy loss
        - Otherwise uses standard binary cross-entropy
        - Sets up a three-stage LearningRateScheduler for epochs 0–30, 31–36, and 37–41
        - Trains for 41 epochs with batch size 41
        - Saves the model under ./models/ with filename pattern {num}_model_{aug}.h5
    -> In __main__:- Loads combined training+validation data from processed_dataset.pickle
        - Trains the extended (aug='e') and original (aug='o') models- Loads augmented datasets from augmented_dataset.pickle and iterates over oversampling levels (25%, 50%, 75%, 100%) to train control ('c'), horizontal ('h'), vertical ('v'), and linear-combination ('lc') models

8. train_weighted_model.py
    -> Wrapper script to train the weighted CNN model with the optimal settings
    -> Imports train_model from train_model.py-> Loads processed data, concatenates X_train_1 & X_val_1 (excluding metadata columns) into X_train_val and y_train_val
    -> Calls train_model(X_train_val, y_train_val, 37, 'w', 0, weighted=1) to fit the weighted-loss model

9.optimal_thresholding.py
    -> Calculates the optimal probability threshold for each functional group to maximize F1-score
    -> Defines optimal_threshold(X_train_val, y_train_val):- Reshapes inputs to (n_samples, 600, 1)
        - Loads the extended model from ../models/0_model_extended.h5- Predicts probabilities on X_train_val
        - For each of the 37 classes:* Computes precision–recall curve and average precision* Calculates F1-score at each threshold and selects the threshold with highest F1
        - Returns a dict mapping each class index to its optimal threshold-> In __main__, loads data and invokes optimal_threshold(...)

10. evaluation.py
    -> Provides comprehensive evaluation metrics for a trained model
    -> Key functions:- model_predict(...): applies either fixed (0.5) or optimal thresholds to predicted probabilities
        - f_score(...): computes per-group F1-score, precision, recall, and orders functional groups by performance
        - emr_fgs(...): calculates non-accumulative and accumulative exact match rates (EMR) based on number of functional groups per sample
        - emr_class(...): computes accumulative EMR as classes are added in order of descending frequency- accuracy(...): measures accuracy for presence vs. absence of each group, and overall positive/negative class balance
        - avg_precision(...): computes average precision for each functional group
    -> In the main block:- Loads data and extended model
        - Computes optimal thresholds, makes predictions, and prints tables for F1-scores, EMRs, average precision, and presence/absence accuracies


============= SCRIPTS ============

Brief description of scripts.

DATA PROCESSING:

preprocessing.py - performs preprocessing of the dataset to be used for model training.
data_augmentation.py - augments the preprocessed dataset (use to create augmented dataset).
split_data.py - splits dataset into training, validation, and test sets.

HYPERPARAMETER OPTIMIZATION:

hyperparameter_optimization.py - finds the optimal hyperparameters for CNN model.

MODEL TRAINING:

train_model.py - trains the model without any weights applied on the loss function.
train_weighted_model.py - trains the model with weighted loss function to balance the unbalanced data.

EVALUATION:

evaluation.py - evaluates the trained model.

OTHER:

smarts.py - shows the defined SMARTS strings for the functional groups considered.
optimal_thresholding.py - calculates the optimal probability threshold for the classification of each functional group.

=========== OTHER INFO ===========

All augmented models are based on the extended list of functional groups.

The augmentation was carried out in 25%, 50%, 75%, 100% of the initial dataset.

The performance analysis of the model was calculated using 0_extended.h5 model.
